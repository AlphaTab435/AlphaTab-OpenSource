@echo off
echo === ShortsForge Daily Automation ===
echo Starting Pipeline...

:: Navigate to the project root
cd /d "%~dp0\..\.."

:: Run the pipeline to generate up to 5 new videos
python scripts/story_maker/run_pipeline.py --no-ai --max-videos 5

echo Pipeline Complete.
echo Starting Uploader...

:: Run the uploader to upload up to 5 videos
python scripts/story_maker/run_upload.py

echo Uploader Complete.
echo Automation Cycle Finished!
pause
