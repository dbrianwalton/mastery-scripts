import csv
import argparse
import subprocess
import os

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
parser.add_argument('--studentData')
parser.add_argument('--masteryData')
parser.add_argument('--outcomeFile')
parser.add_argument('--msgA', default='')
parser.add_argument('--msgB', default='')
parser.add_argument('--tempFile')
parser.add_argument('--skipStudents', default=1)
parser.add_argument('--subject', default='Your Mastery Progress')
args = parser.parse_args()

class Outcome:
    def __init__(self, groupCode, groupTitle, outcomeCode, outcomeTitle, index):
        self.groupCode = groupCode
        self.groupTitle = groupTitle
        self.outcomeCode = outcomeCode
        self.outcomeTitle = outcomeTitle
        self.index = index
    def codeStr(self):
        return (getOutcomeCode(self.groupCode, self.outcomeCode))

class StudentRecord:
    def __init__(self, student_name, student_id):
        self.name = student_name
        self.id = student_id
    def setEmail(self, emailName):
        self.email = emailName + "@dukes.jmu.edu"
    def getEmail(self):
        return self.email
    def setResults(self,student_results):
        self.results = student_results
    def getFirst(self):
        firstName = self.name.split(' ')[0]
        return firstName
    def getLastFirst(self):
        names = self.name.split(' ')
        return ','.join([names[-1], ' '.join(names[:-1])])
    def getLastFirstTight(self):
        names = self.name.split(' ')
        return ''.join([names[-1], ''.join(names[:-1])])

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

def getOutcomeCode(group, outcome):
    return '.'.join([group, outcome])

# Parse the first row of the data table
# Extracts the information for outcome descriptions
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
def generateReport(reportFile, studentRecord):
    numMastered = 0

    def addGroupHeader(groupCode):
        # Display group header information
        group = groups[groupCode]
        reportFile.write(''.join([groupCode, ': ', group['title']]))
        reportFile.write('\n')

    groupCodes = sorted(groups.keys())
    for groupCode in groupCodes:
        # Display group header information when outcome appears.
        needGroupHeader = True
        group = groups[groupCode]
        numInGroup = 0
        totInGroup = 0

        # Go through the outcomes from this group.
        outcomeCodes = sorted(group['outcomes'])
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
                    progress = 'Mastered'
                    numMastered = numMastered + 1
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
        if totInGroup > 0:
            reportFile.write('Mastered Objectives in Group: %d out of %d\n\n' % (numInGroup, totInGroup))

    reportFile.write('Total Number of Mastered Objectives: ' + str(numMastered) + '\n')



# Use the records for the student and the outcomes to generate a report
def prepareEmail(studentRecord):
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
    mailScript = """
    set m to POSIX file "%s"
    set msg to read m
    tell application "Mail"
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
    # For this file, we don't have any use for the header information.
    headers = next(dataStream)
    for i in range(int(args.skipStudents)):
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

for i in order:
    prepareEmail(studentData[i])
