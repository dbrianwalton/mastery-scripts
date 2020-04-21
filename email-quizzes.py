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


parser = argparse.ArgumentParser(description='Import a Canvas mastery export file and produce a summary.')
parser.add_argument('--csv', dest='csvFile')
parser.add_argument('--msg')
parser.add_argument('--subject', default='Your Mastery Quiz')
parser.add_argument('--quizDir')
args = parser.parse_args()

class StudentRecord:
    def __init__(self, student_name, student_id):
        self.name = student_name
        self.id = student_id
    def getLastFirst(self):
        names = self.name.split(' ')
        return ','.join([names[-1], ' '.join(names[:-1])])
    def getLastFirstTight(self):
        names = self.name.split(' ')
        return ''.join([names[-1], ''.join(names[:-1])])

groups = dict()

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

# Use the records for the student and the outcomes to generate a report
def prepareEmail(studentRecord):
    attachment = studentRecord.getLastFirstTight().lower()+".pdf"
    filePath = args.quizDir +"/"+ attachment
    if (os.path.exists(filePath)):
        print(os.path.abspath(filePath))
        address = studentRecord.id + "@dukes.jmu.edu"
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
          tell content of theOutMessage
            make new attachment with properties {file name:"%s"} at after last paragraph
          end tell
        end tell
        """ % ( os.path.abspath(args.msg), address, args.subject, os.path.abspath(filePath) )
        asrun(mailScript.encode())

# Parse the data file to create our desired information
studentData = []
with open(args.csvFile, newline='') as studentInfoFile:
    # Create an iterator to go through the rows on the file.
    dataStream = csv.reader(studentInfoFile)

    # The first row has header information
    # Read and then parse this information into something useful for us.
    headers = next(dataStream)
    for student in dataStream:
        name = student[0]
        id = student[3]
        section = student[4]
        studentRecord = StudentRecord(name, id)
        studentData.append(studentRecord)


numStudents = len(studentData)
# Create a sort order for students base on LastName, FirstName
def nameKey(i):
    return studentData[i].getLastFirst()
nameOrder = sorted([i for i in range(numStudents)], key=nameKey)
order = nameOrder

for i in order:
    prepareEmail(studentData[i])
