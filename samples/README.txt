If you go to the samples folder, you can test this out using the following command lines as examples.

To create quizzes:

> mkdir tmpDir
> python3 ../mastery-quizzes.py --csv Mastery_Sample.csv --outcomes OutcomeList.txt --quiz Quiz_Sample.tex --quizDir tmpDir/ --week 5

To create emailed progress reports:

> python3 ../email-progress.py --studentData samples/Grades_Sample.csv --masteryData samples/Mastery_Sample.csv --outcomeFile samples/OutcomeList.txt --subject "Progress Report"
