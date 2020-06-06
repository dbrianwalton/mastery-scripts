import csv
import argparse
import subprocess
import os
import re

# The script is based on using a Canvas Learning Mastery report export to generate
# a summary for each student that will be emailed.
# The script assumes that there are multiple possible levels of mastery.
# Currently, I am working with Apprentice = 2, Journey = 3, Mastery = 4.
# Anything lower does not count as mastery.
# In addition, I have engagement outcomes that are either satisfied or not satisfied.
# This is a lookup table to put on the label for each outcome and in the final summary.
studentEmailDomain = "@dukes.jmu.edu"
masteryStatus = { 0:'Not Yet', 1:"Satisfied", 2:"Apprentice", 3:"Journey", 4:"Mastery" }

# The script will show the status for each outcome and provide a summary count
# at the end showing totals.

# This script is Mac-specific using Apple Mail, so that messages
# are created as a draft. In text files, I generate a preamble and postamble
# and the automated summary is generated in the middle.
def asrun(ascript):
    "Run the given AppleScript and return the standard output and error."

    osa = subprocess.Popen(['osascript', '-'],
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE)
    return osa.communicate(ascript)[0]

def asquote(astr):
    "Return the AppleScript equivalent of the given string."

    astr = astr.replace('"', '" & quote & "')
    return '"{}"'.format(astr)


parser = argparse.ArgumentParser(description='Import a Canvas gradebook (for student records) and mastery export file (for progress) and produce a summary that is emailed.')
parser.add_argument('--studentData', help='file path, CSV of Canvas grade export to get section information')
parser.add_argument('--masteryData', help='file path, CSV of Canvas learning mastery report')
parser.add_argument('--outcomeFile', help='file path, text file with 4 columns: group code (text), outcome code (text), latex command stem (only alpha), week introduced')
parser.add_argument('--msgA', default='', help='filepath, text message with preamble')
parser.add_argument('--msgB', default='', help='filepath, text message with postamble')
parser.add_argument('--tempFile', default='tmpmsg.txt', help='filepath, location where message is saved before pushing the draft to Mail')
parser.add_argument('--summary', dest='summaryReport', default='', help='filepath, instead of sending emails, create a single summary file of all reports')
parser.add_argument('--skipStudents', type=int, default=0, help='integer, number of students to skip for debugging')
parser.add_argument('--student', default='', help='text, match students to text and only create report for them')
parser.add_argument('--subject', default='Your Mastery Progress', help='text, emailer subject line')
args = parser.parse_args()

# Some structure to keep track of outcomes, organized by groups.
class Outcome:
    def __init__(self, groupCode, groupTitle, outcomeCode, outcomeTitle, index):
        self.groupCode = groupCode
        self.groupTitle = groupTitle
        self.outcomeCode = outcomeCode
        self.outcomeTitle = outcomeTitle
        self.index = index
    def codeStr(self):
        return (getOutcomeCode(self.groupCode, self.outcomeCode))

# Some structure to keep track of who a student is and what they have done.
class StudentRecord:
    def __init__(self, student_name, student_id):
        self.name = student_name
        self.id = student_id
        self.hasResults = False
    def setEmail(self, emailName):
        self.email = emailName + studentEmailDomain
    def getEmail(self):
        return self.email
    def setResults(self,student_results):
        self.results = student_results
        self.hasResults = True
    def getFirst(self):
        firstName = self.name.split(' ')[0]
        return firstName
    def getLastFirst(self):
        names = self.name.split(' ')
        return ','.join([names[-1], ' '.join(names[:-1])])
    def getLastFirstTight(self):
        names = self.name.split(' ')
        return ''.join([names[-1], ''.join(names[:-1])])

# Groups are where learning outcomes are organized
# On Canvas, I have learning outcomes grouped into a hierarchy
# Each group has a simple code and a descriptor
# For example "G1: Functions"
# The script uses the G1 as the group code and Functions as the title.
# Similarly, an outcome has a code and a title in a similar vein.
# For example "F1: Defining Functions"
# The outcome code would be F1 and the title would be Defining Functions
groups = dict()
outcomeArray = []
outcomeDict = dict()
def addOutcome(outcome):
    code = outcome.codeStr()
    outcomeDict[code] = outcome
    outcomeArray.append(outcome)
    group = groups.get(outcome.groupCode, { 'title':outcome.groupTitle, 'outcomes': [] })
    group['outcomes'].append(outcome.outcomeCode)
    groups[outcome.groupCode] = group

# In the script, outcomes have both a group and outcomes
# This allows us to sort by groups if desired.
# Using the example above, this function would return "G1.F1" as the outcome code.
def getOutcomeCode(group, outcome):
    return '.'.join([group, outcome])

# Parse the first row of the data table
# Extracts the information for outcome descriptions
# My Outcome Titles include the Outcome and Title, so we pull this off for tracking.
def parseMasteryHeader(headers):
    # Canvas exports outcome information in the headers.
    # Column 1: Student Name
    # Column 2: Student # ID
    # Pairs of columns:
    #  "Outcome_Title result"
    #  "Outcome_Title mastery points"
    numberOutcomes = (len(headers)-2)//2
    for i in range(numberOutcomes):
        col = 2+2*i
        outcome = headers[col]
        # Group title separated from Outcome title by '>'
        parts = outcome.split('>')

        # Group and outcome titles use ShortCode: Title
        groupInfo = [ text.strip() for text in parts[0].split(':') ]
        groupCode = groupInfo[0]
        groupTitle = ': '.join(groupInfo[1:])

        outcomeInfo = [ text.strip() for text in parts[1].split(':') ]
        outcomeCode = outcomeInfo[0]
        outcomeTitle = ': '.join(outcomeInfo[1:])
        # Remove the ' result' from end of title
        outcomeTitle = outcomeTitle[:-7]

        # Generate the outcome record
        outcome = Outcome(groupCode, groupTitle, outcomeCode, outcomeTitle, i)
        addOutcome(outcome)

# Parse one row of the table corresponding to a student's mastery record
# The ordering of columns is described above in parseHeader
def parseMasteryRow(studentMasteryRow):
    # Column 1: name
    name = studentMasteryRow[0]
    # Column 2: student_id
    id = studentMasteryRow[1]

    # Recall the student's record.
    studentRecord = studentsByID.get(id, StudentRecord(name, id))

    # Remaining columns in pairs corresponding to mastery data
    # - points earned
    # - required for mastery
    numOutcomes = (len(studentMasteryRow)-2)//2
    results = []
    for i in range(numOutcomes):
        k = 2+2*i
        mastered = False
        if len(studentMasteryRow[k])==0:
            score = 0.0
        else:
            score = float(studentMasteryRow[k])
        if len(studentMasteryRow[k+1])==0:
            required = 0.0
        else:
            required = float(studentMasteryRow[k+1])
        results.append({ 'score': score, 'mastery': (score >= required) })
    studentRecord.setResults(results)
    return studentRecord

# Generate the portion of the email that comes from the summary of outcomes.
# This follows the preamble file and will be followed by a postamble.
# Outcomes are grouped together by Group code and sorted by outcome codes.
# A final summary is at the end.
def generateReport(reportFile, studentRecord):
    numMastered = 0
    masteryPoints = 0
    masteryCount = { 1:0, 2:0, 3:0, 4:0 }

    # Each new group, we want to include a header line to the report
    def addGroupHeader(groupCode):
        # Display group header information
        group = groups[groupCode]
        reportFile.write(''.join([groupCode, ': ', group['title']]))
        reportFile.write('\n')

    # Pull out the group/outcome code information for sorting.
    def outcomeGroup(outcomeCode):
        matches = re.search('\A([A-Za-z]*)', outcomeCode)
        return(matches.group(0))
    def outcomeCount(outcomeCode):
        matches = re.search('\A([A-Za-z]*)([0-9]*)', outcomeCode)
        return(int(matches.group(2)))
    def outcomeSuffix(outcomeCode):
        matches = re.search('\A([A-Za-z]*)([0-9]*)(.*)', outcomeCode)
        return(matches.group(3))

    groupCodes = sorted(groups.keys())
    for groupCode in groupCodes:
        # Display group header information when outcome appears.
        needGroupHeader = True
        group = groups[groupCode]
        numInGroup = 0
        totInGroup = 0

        # Go through the outcomes from this group.
        outcomeCodes = sorted(group['outcomes'], key=outcomeSuffix)
        outcomeCodes = sorted(outcomeCodes, key=outcomeCount)
        for outcomeCode in outcomeCodes:
            code = getOutcomeCode(groupCode, outcomeCode)
            # See if this outcome is to be included
            if code in useOutcomeDict:
                # Is this the first included outcome for the group?
                if needGroupHeader:
                    addGroupHeader(groupCode)
                    needGroupHeader = False

                # Now generate the output for this outcome.
                # Also update the overall statistics for the outcome
                totInGroup = totInGroup + 1
                outcome = outcomeDict[code]
                outcomeStat = outcomeStats[code]
                progress = ''
                # See if this is a partial progress problem.
                hasPartial = False
                if code in partialOutcomeDict:
                    hasPartial = True
                    partial = outcomeDict[partialOutcomeDict[code]]
                    partialProgress = studentRecord.results[partial.index]['mastery']
                if studentRecord.results[outcome.index]['mastery']:
                    score = int(studentRecord.results[outcome.index]['score'])
                    progress = masteryStatus[score]
                    masteryCount[score] = masteryCount[score] + 1
                    numMastered = numMastered + 1
                    masteryPoints = masteryPoints + score
                    numInGroup = numInGroup + 1
                    outcomeStat[0] = outcomeStat[0] + 1
                else:
                    outcomeStat[1] = outcomeStat[1] + 1
                    if hasPartial:
                        if partialProgress:
                            progress = '1/2'
                        else:
                            progress = '0/2'
                outcomeStats[code] = outcomeStat
                reportFile.write(''.join(['  ', outcomeCode, ' ', outcome.outcomeTitle,': ', progress]))
                reportFile.write('\n')
        #if totInGroup > 0:
        #    reportFile.write('Mastered Objectives in Group: %d out of %d\n' % (numInGroup, totInGroup))
        reportFile.write('\n')
    reportFile.write('\nOverall Summary:\n')
    for score in [1, 2, 3, 4]:
        if masteryCount[score] > 0:
            reportFile.write('  Number of "%s" outcomes (%d pt each): %d\n' % (masteryStatus[score], score, masteryCount[score]))
    reportFile.write('Total Number of Mastery Points: ' + str(masteryPoints) + '\n')

def prepareSummary(order):
    with open(args.summaryReport, 'w') as reportStream:
        for i in order:
            studentRecord = studentData[i]
            if (args.student == '' or studentRecord.name.lower().find(args.student.lower()) >= 0):
                if not studentRecord.hasResults:
                    reportStream.write(studentRecord.name + " (No Results)\n\n")
                    continue
                reportStream.write(studentRecord.name + '\n')
                generateReport(reportStream, studentRecord)
                reportStream.write('\n\n\n')

# Use the records for the student and the outcomes to generate a report
# This uses three parts for each email, joined together as a text file.
# Saluation + Preamble + GeneratedReport + Postamble
def prepareEmail(studentRecord):
    if not studentRecord.hasResults:
        print(studentRecord.name, " (No Results)\n")
        return
    print(studentRecord.name,'\n')
    with open(args.tempFile, 'w') as messageStream:
        messageStream.write("Dear %s,\n\n" % (studentRecord.getFirst()))
        if len(args.msgA) > 0:
            with open(args.msgA,'r') as messageText:
                for line in messageText:
                    messageStream.write(line)
        generateReport(messageStream, studentRecord)
        if len(args.msgB) > 0:
            with open(args.msgB,'r') as messageText:
                for line in messageText:
                    messageStream.write(line)

    address = studentRecord.getEmail()

    # Here is the platform specific stuff -- I couldn't get direct Python email
    # to work, so I used Applescript to send the message to Mail as a draft,
    # which I could then send. (It is possible to send directly from Applescript,
    # but that made me nervous.
    # To send directly, add a line
    # send
    # immediately after "set content to msg"
    mailScript = """
    set m to POSIX file "%s"
    set msg to read m
    tell application "Mail"
      activate
      set theOutMessage to make new outgoing message with properties {visible:true}
      tell theOutMessage
          make new to recipient at end of to recipients with properties {address:"%s"}
          set sender to "D. Brian Walton <waltondb@jmu.edu>"
          set subject to "%s"
          set content to msg
      end tell
    end tell
    """ % ( os.path.abspath(args.tempFile), address, args.subject )
    asrun(mailScript.encode())

# Parse the data files to create our desired information
# Parse the gradebook file that contains names and email-ids (does not have mastery)
studentData = []
studentsByID = {}
with open(args.studentData, newline='') as studentInfoFile:
    # Create an iterator to go through the rows on the file.
    dataStream = csv.reader(studentInfoFile)

    # The first row has header information
    # For this file, we don't have any use for the header information
    # so that row is always skipped. Can then skip additional rows
    # using the skipStudents debugging option.
    headers = next(dataStream)
    for i in range(1+args.skipStudents):
        next(dataStream)
    # Read each student record to identify students and email addresses.
    for student in dataStream:
        name = student[0]
        id = student[1]
        emailName = student[3]
        section = student[4]
        studentRecord = StudentRecord(name, id)
        studentRecord.setEmail(emailName)
        studentData.append(studentRecord)
        studentsByID[id] = studentRecord

# Now parse the mastery report export file.
# This is going to contain student progress but not email or section information.
with open(args.masteryData, newline='') as masteryFile:
    # Create an iterator to go through the rows on the file.
    dataStream = csv.reader(masteryFile)

    # The first row has header information
    # Read and then parse this information into something useful for us.
    # This means identify where objectives are found in the file.
    # (Canvas creates an unpredictable ordering)
    headers = next(dataStream)
    parseMasteryHeader(headers)

    # All other rows are individual student records
    # Read each row and process into a student progress record
    for studentRow in dataStream:
        parseMasteryRow(studentRow)

# Load the information about which outcomes have been included.
# Parse the restricted set of outcomes that will be included.
useOutcomes = []
useOutcomeDict = dict()
# For outcomes that require multiple completions, track partials.
partialOutcomeDict = dict()
outcomeStats = dict()
with open(args.outcomeFile, 'r') as outcomeFile:
    outcomeStream = csv.reader(outcomeFile, delimiter='\t')
    for row in outcomeStream:
        if len(row)==0:
            continue
        # Supplemental information is contained in optional column 5
        partialCode = ""
        if len(row) > 4:
            if row[4] == "skip":
                continue
            else:
                partialCode = row[4]

        objCode = getOutcomeCode(row[0], row[1]);
        useOutcomeDict[objCode] = len(useOutcomes)
        outcomeStats[objCode] = [0, 0] # pass/not yet
        useOutcomes.append(row)
        if len(partialCode) > 0:
            partialOutcomeDict[objCode] = partialCode

numStudents = len(studentData)
# Create a sort order for students base on LastName, FirstName
def nameKey(i):
    return studentData[i].getLastFirst()
nameOrder = sorted([i for i in range(numStudents)], key=nameKey)
order = nameOrder

if (len(args.summaryReport) > 0):
    prepareSummary(order)
else:
    for i in order:
        if (args.student == '' or studentData[i].name.lower().find(args.student.lower()) >= 0):
            prepareEmail(studentData[i])
