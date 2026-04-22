# `workday-sync`

This project converts workday.com absence requests into calendar files that can be imported into Outlook/Google/Apple Calendar. It's intended to let you easily block out your work calendar with absences you've entered into Workday.

It is an intentionally over-engineered Python module - I am learning how to use Claude Code effectively, so although this could have been a simple bash script, it's a fully TDD'd Python module that can be installed on your system.

To use:

1. Log into your Workday account, go to "Absences", then "View - My Absence". Click the icon to download your absences as an Excel file, and you'll get a "Your_Name.xlsx" file
2. Clone this repository, cd into it, and run `uv install .` (This project requires `uv` and `pyenv`, which can be installed on mac with `brew install uv pyenv`)
3. Find your downloaded file, and run `workday-sync convert Your_Name.xlsx -o pto.ics`
4. Open `pto.ics` in your calendar app and import the generated events.

It expects full days of PTO to be entered as 8-hour days. If you've entered a different amount of time, the tool will look for keywords in the absence description to establish when the leave is.

It has time zone support, which defaults to London. Run `workday-sync convert --help` to see all the options available.
