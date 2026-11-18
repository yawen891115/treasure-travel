# Treasure Travel trip survey (copy these questions into Google Forms)

Use the exact question titles below: `scripts/survey_to_requests.py` looks for them.

| # | Question title (exact) | Google Forms type | Options |
|---|---|---|---|
| 1 | How many people are in your group? | Multiple choice | 1, 2, 3, 4 |
| 2 | Which day would you go? | Dropdown | Monday ... Sunday |
| 3 | What time would you start? | Time | |
| 4 | What time would you finish? | Time | |
| 5 | Total budget for the group (USD) | Short answer (number) | |
| 6 | What do you enjoy? (pick up to 3) | Checkboxes | Art, History, Nature, Coffee, Seafood, Pizza, Nightlife, Shopping, Family |
| 7 | How would you get around? | Multiple choice | Walking, Car |
| 8 | Longest travel time you accept between stops (minutes) | Multiple choice | 10, 15, 20, 30 |
| 9 | Where would you start? (a place name) | Short answer | |
| 10 | How many stops would you like? | Multiple choice | 3, 4, 5 |
| 11 | What annoys you most about planning a day trip today? | Paragraph | |
| 12 | Would you use an app that plans the day for you? | Linear scale 1-5 | |

Questions 1-10 become test requests for the agent. Questions 11-12 are product feedback:
read them, group similar answers, and turn the most common ones into product requirements.
