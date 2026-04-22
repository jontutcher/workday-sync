# Workday->Google Calendar Sync

This project will create an application that takes a list of annual leave from the Workday UI (https://wd501.myworkday.com/), and turns it into an ICS file for importing into Google Calendar. Here are the initial requirements; ask for clarification and suggest improvements.

- Must take, as input, the user's PTO as entered into workday, as an XLSX file. There is an example XLSX file in the project as "test_pto.xlsx"
- Could automatically download this file from Workday, given a user's corporate email address, if it's possible (the test file is from the "my absence" page at https://wd501.myworkday.com/chainguard/d/task/2997$12368.htmld, and the path to download it is https://wd501.myworkday.com/chainguard/doc-ready/0key.xlsx?docName=Jon_Tutcher.xlsx&instance-id=2997%2412368).
- Must produce a static Google Calendar-compatible ICS file that can be imported into Google Calendar to show PTO.
- Must be time-zone aware. If there's no time zone info, ask the user what time zone their PTO is in.
- If possible, should create both standard events in Google Calendar, as well as "Out of Office" events.
- Events should be titled "[User name] - PTO"
- Where the duration of the leave is 8 hours, it should be assumed that they are on leave all day, and the resulting ICS file event should actually run from 0800 - 1800 since it represents a whole day off
- Where the duration of the leave is less than 8 hours, check the "comment" field to see whether it's morning or afternoon. Search for phrases like "morning", "afternoon", "AM", and "PM"
- Use a modern python stack - `uv` and `pyenv`. Structure the project according to modern best practice. It should be installable as a Python module. Use type hinting.
- Use a command line interface, and include a help file. Use the "click" python library to do this.
- Write the application using TDD. Use pytest.
- Create a plan first, including a detailed architecture document and implementation plan.
- Ask if you are unsure of anything.
- Create a git repo and commit as you go.
