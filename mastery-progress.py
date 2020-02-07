import csv
import argparse

parser = argparse.ArgumentParser(description='Import a Canvas mastery export file and produce a summary.')
parser.add_argument('--csv', dest='csvFile')
parser.add_argument('--outcomes', dest='outcomeFile')
parser.add_argument('--quiz', dest='quizInclude', default='')
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
def parseHeader(headers):
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
def parseRow(studentRecord):
    # Column 1: name
    name = studentRecord[0]
    # Column 2: student_id
    id = studentRecord[1]

    # Remaining columns in pairs corresponding to mastery data
    # - points earned
    # - required for mastery
    numOutcomes = (len(studentRecord)-2)//2
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

# Use the records for the student and the outcomes to generate a report
def generateReport(studentRecord):
    # Display student header information
    print(studentRecord.name)

    groupCodes = sorted(groups.keys())
    for groupCode in groupCodes:
        # Display group header information
        group = groups[groupCode]
        print(groupCode, ': ', group['title'], sep='')

        # Go through the outcomes from this group.
        outcomeCodes = sorted(group['outcomes'])
        for outcomeCode in outcomeCodes:
            code = getOutcomeCode(groupCode, outcomeCode)
            outcome = outcomeDict[code]
            progress = ''
            if studentRecord.results[outcome.index]['mastery']:
                progress = 'Mastered'
            print('  ', outcomeCode, ' ', outcome.outcomeTitle,': ', progress, sep='')

# Use the records for the student and the outcomes to generate a new quiz
def generateQuiz(quizFile, studentRecord):
    # Display student header information
    quizFile.write('{\\flushright \\textbf{')
    quizFile.write(studentRecord.name)
    quizFile.write('}}\n\n')

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


# Parse the data file to create our desired information
with open(args.csvFile, newline='') as masteryFile:
    # Create an iterator to go through the rows on the file.
    dataStream = csv.reader(masteryFile)

    # The first row has header information
    # Read and then parse this information into something useful for us.
    headers = next(dataStream)
    parseHeader(headers)

    # All other rows are individual student records
    studentData = [ parseRow(row) for row in dataStream ]

# Parse the restricted set of outcomes to include.
useOutcomes = []
with open(args.outcomeFile, 'r') as outcomeFile:
    outcomeStream = csv.reader(outcomeFile, delimiter='\t')
    for row in outcomeStream:
        useOutcomes.append(row)

# Create a sort order for students base on LastName, FirstName
def nameKey(i):
    return studentData[i].getLastFirst()
numStudents = len(studentData)
order = sorted([i for i in range(numStudents)], key=nameKey)

# Now work through the students in the generated order
#for i in order:
#    generateReport(studentData[i])

if args.quizInclude != '':
    with open(args.quizInclude, 'w') as quizIncludeFile:
        for i in order:
            generateQuiz(quizIncludeFile, studentData[i])
