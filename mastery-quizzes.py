import csv
import argparse
import subprocess

parser = argparse.ArgumentParser(description='Import a Canvas mastery export file and produce a summary.')
parser.add_argument('--csv', dest='csvFile')
parser.add_argument('--outcomes', dest='outcomeFile')
parser.add_argument('--quiz', dest='quizInclude')
parser.add_argument('--quizDir')
parser.add_argument('--week', dest='week', type=int, default=0)
parser.add_argument('--generic')
parser.add_argument('--students', dest='studentData', default='')
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
    def __init__(self, student_name, student_id, student_results):
        self.name = student_name
        self.id = student_id
        self.results = student_results
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
def parseHeader(headers, numberOutcomes):
    # Canvas exports outcome information in the headers.
    # Column 1: Student Name
    # Column 2: Student # ID
    # Pairs of columns:
    #  "Outcome_Title result"
    #  "Outcome_Title mastery points"
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
def parseRow(studentRecord, numOutcomes):
    # Column 1: name
    name = studentRecord[0]
    # Column 2: student_id
    id = studentRecord[1]

    # Remaining columns in pairs corresponding to mastery data
    # - points earned
    # - required for mastery
    results = []
    for i in range(numOutcomes):
        k = 2+2*i
        mastered = False
        if len(studentRecord[k])==0:
            score = 0.0
        else:
            score = float(studentRecord[k])
        if len(studentRecord[k+1])==0:
            required = 0.0
        else:
            required = float(studentRecord[k+1])
        results.append({ 'score': score, 'mastery': (score >= required) })

    record = StudentRecord(name, id, results)
    return record

def BlankStudent(numOutcomes):
    results = []
    for i in range(numOutcomes):
        results.append({ 'score': 0.0, 'mastery': False })

    record = StudentRecord('Problem Template', '', results)
    return record

# Use the records for the student and the outcomes to generate a report
def generateReport(reportFile, studentRecord):
    # Display student header information
    reportFile.write(studentRecord.name)
    reportFile.write('\n')
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
                outcome = outcomeDict[code]
                outcomeStat = outcomeStats[code]
                progress = ''
                if studentRecord.results[outcome.index]['mastery']:
                    progress = 'Mastered'
                    numMastered = numMastered + 1
                    outcomeStat[0] = outcomeStat[0] + 1
                else:
                    outcomeStat[1] = outcomeStat[1] + 1
                outcomeStats[code] = outcomeStat

                reportFile.write(''.join(['  ', outcomeCode, ' ', outcome.outcomeTitle,': ', progress]))
                reportFile.write('\n')
    reportFile.write('Total Number of Mastered Objectives: ' + str(numMastered) + '\n')
    reportFile.write('\n\n----------------\n\n')

def generateStatisticsReport(reportFile):
    groupCodes = sorted(groups.keys())
    for groupCode in groupCodes:
        # Display group header information when outcome appears.
        needGroupHeader = True
        group = groups[groupCode]

        # Go through the outcomes from this group.
        outcomeCodes = sorted(group['outcomes'])
        for outcomeCode in outcomeCodes:
            code = getOutcomeCode(groupCode, outcomeCode)
            if code in useOutcomeDict:
                stats = outcomeStats[code]
                reportFile.write("%s: Passed = %d, Not Yet=%d\n" % (code, stats[0], stats[1]))

# Use the records for the student and the outcomes to generate a new quiz
def generateQuiz(studentRecord):
    with open('Questions.tex', 'w') as quizFile:
        # Display student header information
        quizFile.write('\\setcounter{page}{1}\n\\markright{')
        #quizFile.write('{\\flushright \\textbf{')
        quizFile.write(studentRecord.name)
        if args.studentData != '':
            section = studentSections.get(studentRecord.name, "Both")
            quizFile.write(' (' + section + ')')
        quizFile.write('}\n\n')

        quizFile.write('\\header\n\n')
        quizFile.write('\\begin{enumerate}\n')

        # Identify which outcomes already are passed.
        masteredList = []
        for outcomeRow in useOutcomes:
            code = getOutcomeCode(outcomeRow[0], outcomeRow[1])
            outcome = outcomeDict[code]
            if studentRecord.results[outcome.index]['mastery']:
                masteredList.append(outcome.outcomeCode)

        quizFile.write('\\objMastery{')
        quizFile.write(', '.join(masteredList))
        quizFile.write('}\n\n')

        # Then add all of the problems not mastered.
        for outcomeRow in useOutcomes:
            code = getOutcomeCode(outcomeRow[0], outcomeRow[1])
            outcome = outcomeDict[code]
            if not studentRecord.results[outcome.index]['mastery']:
                quizFile.write('\\obj')
                quizFile.write(outcomeRow[2])
                quizFile.write('{}\n')
                masteredList.append(outcome.outcomeCode)
        quizFile.write('\\end{enumerate}\n\n\\cleardoublepage \n\n')
    # Now that the problems were generated, run pdflatex to create the quiz.
    print(args.quizDir, args.quizInclude)
    process = subprocess.run(['pdflatex',
        '-jobname',studentRecord.getLastFirstTight().lower(),
        '-output-directory', args.quizDir,
        args.quizInclude])

# Parse the data file to create our desired information
with open(args.csvFile, newline='') as masteryFile:
    # Create an iterator to go through the rows on the file.
    dataStream = csv.reader(masteryFile)

    # The first row has header information
    # Read and then parse this information into something useful for us.
    headers = next(dataStream)
    numberOutcomes = (len(headers)-2)//2
    parseHeader(headers, numberOutcomes)

    # All other rows are individual student records
    studentData = [ parseRow(row, numberOutcomes) for row in dataStream ]

# Parse the student data file to organize the printing
if (args.studentData != ''):
    studentSections = dict()
    with open(args.studentData, newline='') as studentInfoFile:
        # Create an iterator to go through the rows on the file.
        dataStream = csv.reader(studentInfoFile)

        # The first row has header information
        # Read and then parse this information into something useful for us.
        headers = next(dataStream)
        for student in dataStream:
            name = student[0]
            section = student[4]
            studentSections[name] = section

# Parse the restricted set of outcomes that will be included.
useOutcomes = []
useOutcomeDict = dict()
outcomeStats = dict()
with open(args.outcomeFile, 'r') as outcomeFile:
    outcomeStream = csv.reader(outcomeFile, delimiter='\t')
    for row in outcomeStream:
        # Week when objective is introduced is stored in column 4 (index 3)
        if args.week == 0 or int(row[3]) <= args.week:
            objCode = getOutcomeCode(row[0], row[1]);
            useOutcomeDict[objCode] = len(useOutcomes)
            outcomeStats[objCode] = [0, 0] # pass/not yet
            useOutcomes.append(row)

# Create a sort order for students base on LastName, FirstName
def nameKey(i):
    return studentData[i].getLastFirst()
def sectionNameKey(i):
    section = studentSections[studentData[i].name]
    return section + studentData[i].getLastFirst()
numStudents = len(studentData)
nameOrder = sorted([i for i in range(numStudents)], key=nameKey)

order = nameOrder
if (args.studentData != ''):
    print("Using sections for sorting.")
    order = sorted([i for i in range(numStudents)], key=sectionNameKey)

for i in order:
    generateQuiz(studentData[i])
generateQuiz(BlankStudent(numberOutcomes))
