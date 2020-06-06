If you go to the samples folder, you can test this out using the following command lines as examples.

To create quizzes:

> mkdir tmpDir
> python3 ../mastery-quizzes.py --csv Mastery_Sample.csv --outcomes OutcomeList.txt --quiz Quiz_Sample.tex --quizDir tmpDir/ --week 5

To create emailed progress reports:

> python3 ../progress-reports.py --studentData Grades_Sample.csv --masteryData Mastery_Sample.csv --outcomeFile OutcomeList.txt --subject "Progress Report"

To create a single summary progress report as a file:

> python3 ../progress-reports.py --studentData Grades_Sample.csv --masteryData Mastery_Sample.csv --outcomeFile OutcomeList.txt --summary SummaryReport.txt