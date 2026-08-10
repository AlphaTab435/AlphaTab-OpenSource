# AutoApply: Automated AI Job Assistant

This project is your personal Automated AI Job Assistant. Its purpose is to save you hundreds of hours of scrolling through LinkedIn by finding jobs, filtering out the bad ones, and using AI to score the remaining ones against your specific resume.

## Documentation
For in-depth explanations of how the project works, please read the documentation files in the `docs/` folder:
- [System Design & Architecture](docs/SYSTEM_DESIGN.md) (Explains the 5-step pipeline and the Fallback/Error Handling system).
- [API Setup Guide](docs/API_SETUP.md) (Step-by-step instructions on getting your free Groq and OpenRouter keys).

---

## How to Run the Project

Open your terminal and make sure you are in the project folder. Here are the commands you use to run the assistant:

### Step 1: Parse Your Resume (Do this once)
Before you do anything else, you must tell the AI about your experience.
```bash
python run.py parse-resume data/Muhammad_Tabish_CV.pdf
```
*(You only need to run this command once, unless you update your PDF file later).*

### Step 2: Run the Whole Pipeline (The Easy Way)
To automatically Search LinkedIn, Pre-Filter, AI Score, and Export the best jobs all in one single command:
```bash
python run.py all
```

### Step 3: Test the Pipeline (Test Mode)
If you just want to test if the pipeline is working without using up your API limits, you can run:
```bash
python run.py all --limit 1 --max-jobs 1
```
- `--limit 1`: Tells the Scraper to randomly pick exactly *one* search query (instead of doing all of them) to avoid rate limits.
- `--max-jobs 1`: Tells the AI to safely stop after scoring exactly *one* job (so you don't burn through your daily AI quota).

### Running Steps Individually (Optional)
If you want to run specific parts of the pipeline manually instead of using `all`:

1. **Search LinkedIn:** Scrapes jobs and saves them to the database as "discovered".
   ```bash
   python run.py search-jobs
   ```

2. **Score the Jobs:** Asks the AI to read the "discovered" jobs and give them a match score.
   ```bash
   python run.py score
   ```

3. **Export the Best Matches:** Generates the final Excel/CSV file with links to apply.
   ```bash
   python run.py export
   ```

4. **Check Status:** Want to see how many jobs are currently in your database waiting to be reviewed?
   ```bash
   python run.py status
   ```

### After Exporting: Review & Import
1. Open the exported CSV file in Excel or Google Sheets.
2. Click the URLs and apply to the best jobs.
3. Use the "Applied" column to manage jobs:
   - Type **"yes"** (or "y") for jobs you successfully applied to.
   - Type **"no"** (or "n") for useless jobs you want to permanently skip.
   - Leave it **blank** if you aren't sure and want to review it again later.
4. Save the CSV file and tell the bot to update the database:
   ```bash
   python run.py import-applied data/jobs_export_YOUR_DATE.csv
   ```
   *Any job marked "yes" or "no" will never be exported again!*
