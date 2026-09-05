# תרומה לפרויקט

## לפני שמתחילים

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

אפשר לפתח את רוב הפרויקט **בלי החומרה**. כל הבדיקות העצמיות רצות על מחשב רגיל.

## הכללים

1. **בדיקה עצמית לכל לוגיקה לא טריוויאלית.** לא נדרשת מסגרת בדיקות — פונקציית
   `demo()` עם `assert` שנכשלת אם הלוגיקה נשברת. ראה `wall_map.py`.
2. **אין סודות בקוד.** מפתחות מגיעים מקובץ או ממשתנה סביבה בלבד.
3. **אין מספרי חומרה קשיחים.** כל פרמטר של הלוח מגיע מ־`config/`.
4. **עברית היא שפת הממשק.** UTF-8 בכל מקום, RTL בכל UI.
5. **המנוע לא נעצר.** הרנדרר חייב להישאר חי גם כשהמוח או הרשת נופלים.

## איך שולחים שינוי

```bash
git checkout -b my-change
# עובדים, מריצים את הבדיקות
git commit -m "מה שינית ולמה"
git push origin my-change
```

ואז פותחים Pull Request. הענף הראשי מוגן — שינוי נכנס רק אחרי אישור.

## הבדיקות

```bash
.venv\Scripts\python wall_map.py
.venv\Scripts\python golem_app.py --selftest
.venv\Scripts\python -m senses.minds --selftest
.venv\Scripts\python -m senses.social --selftest
```
