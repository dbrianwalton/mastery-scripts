import csv
import argparse
import subprocess

parser = argparse.ArgumentParser(description='Import a Canvas mastery export file and produce a summary.')
parser.add_argument('--csv', dest='csvFile', help='file path, CSV of Canvas learning mastery report')
parser.add_argument('--outcomes', dest='outcomeFile', help='file path, text file with 4 columns: group code (text), outcome code (text), latex command stem (only alpha), week introduced')
parser.add_argument('--quiz', dest='quizInclude', help='file name, latex source for quiz generation')
parser.add_argument('--quizDir', help='folder path, where student quizzes are saved')
parser.add_argument('--week', dest='week', type=int, default=0, help='integer, include all weeks up to this value')
parser.add_argument('--students', dest='studentData', default='', help='file path, CSV of Canvas grade export to get section information')
parser.add_argument('--doneScore', type=int, default=3, help='integer, skip problems of outcomes if already achieve this')
parser.add_argument('--apprenticeScore', type=int, default=2, help='integer, mark problems of outcomes if at this level')
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
# The ordering of columns is described above in parseHeader
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
        results.append({ 'score': score, 'mastery': (score >= args.doneScore) })

    record = StudentRecord(name, id, results)
    return record

# I like to have a template quiz generated.
# So this creates the fake student where that will be used.
def BlankStudent(numOutcomes):
    results = []
    for i in range(numOutcomes):
        results.append({ 'score': 0.0, 'mastery': False })

    record = StudentRecord('Problem Template', '', results)
    return record

# Use the records for the student and the outcomes to generate a new quiz
# The LaTeX file in args.quizInclude needs to have in the preamble
# a definition of every problem as a \newcommand.
# To match outcomes, the OutcomeList.txt file in args.outcome
# defines a LaTeX stem for each outcome. The command defined in the LaTeX
# adds a prefix \obj. The stem can not include numeric symbols, so I use Roman
# numerals. For example, "F1" would have a command \objFI and "FI" would be in
# the 3rd column of the Mastery Outcomes text file.
# In the body of the LaTeX file, we need to include the "Questions.tex" file.
# So here is the document body:
#\begin{document}
#\pagestyle{myheadings}
#\raggedbottom
#\include{Questions}
#\end{document}
#
def generateQuiz(studentRecord):
    # Create a personalized quiz for each student.
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

        if len(masteredList) > 0:
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
                if studentRecord.results[outcome.index]['score'] == args.apprenticeScore:
                    quizFile.write('{ (A)}\n')
                else:
                    quizFile.write('{}\n')
                masteredList.append(outcome.outcomeCode)
        quizFile.write('\\end{enumerate}\n\n\\cleardoublepage \n\n')
    # Now that the problems were generated, run pdflatex to create the quiz.
    print(args.quizDir, args.quizInclude)
    process = subprocess.run(['pdflatex',
        '-jobname',studentRecord.getLastFirstTight().lower(),
        '-output-directory', args.quizDir,
        args.quizInclude])

# Here is where the real work takes place.
# First load the file containing mastery data from Canvas report export.
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

# Second, read information about students and which sections they are in.
# It gets printed in the header for convenience on paper copies
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
# This is reading the tab-delimited text file summarizing outcome information.
# GroupCode \t OutcomeCode \t LateX_stem \t Week_Introduced
# An example line might be as follows
# G1 \t F1 \t FI \t 2
# This would mean that outcome F1 from group G1 began assessment on quiz 2 (week)
# Further, the LaTeX quiz is using \objFI as the command defining the problem
# that will be included.
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

# We will generate the quizzes in student order
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
# The template quiz will be generated last.
generateQuiz(BlankStudent(numberOutcomes))
