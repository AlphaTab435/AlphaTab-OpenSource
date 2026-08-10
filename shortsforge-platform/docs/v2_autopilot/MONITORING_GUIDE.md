# Server Monitoring Guide

This guide provides the essential commands to monitor your headless Ubuntu server's health, including CPU, RAM, Disk Space, and I/O speeds.

## 1. Checking the Live Logs
If your cron job is running in the background, you can watch its output live without disrupting it.
```bash
tail -f /home/ubuntu/shortsforge/data/cron.log
```
*Press `Ctrl + C` to stop watching.*

## 2. Monitoring CPU & RAM 
If you want to see a live dashboard of your system (including per-process usage), use `htop`:
```bash
htop
```
*Press `q` or `Ctrl + C` to exit.*

If you just want a clean, instant printout of your **Total RAM** usage (without all the confusing process lists), use:
```bash
free -h
```
*(The `-h` makes it Human Readable in GBs!)*

If you want a clean, instant printout of your **Total CPU** usage, use:
```bash
top -bn1 | grep "Cpu"
```
*How to read this:* Look for the number right before **`id`** (which stands for Idle). If it says `98.0 id`, it means your CPU is 98% idle (so you are only using 2% of your CPU).

## 3. Monitoring Disk Space (`df -h`)
To see exactly how much of your 100GB hard drive is full, use the Disk Free command:
```bash
df -h /
```
> [!NOTE]
> The `-h` flag stands for "Human Readable". It automatically converts the raw bytes into Gigabytes (G) and provides a clean percentage (e.g., `14% Use`). It is exactly what you are looking for!

## 4. Monitoring Disk I/O (Input/Output Speed)
Disk I/O tells you how fast your server is reading and writing files. `df -h` only shows disk *capacity*, it does NOT show disk speed. If you want to check your I/O speed, you must use one of these two methods:

### Method A: Oracle Cloud Console (Easiest)
1. Log into your Oracle Cloud dashboard.
2. Go to **Compute** -> **Instances** -> Click your server.
3. Scroll down to the **Metrics** section. You will see beautiful visual graphs for **Disk Read** and **Disk Write** speeds over time.

### Method B: Linux Terminal (`iotop`)
If you want to see live I/O speed directly in the terminal just like `htop`, you can use `iotop`.
```bash
# Install it once
sudo apt update && sudo apt install -y iotop

# Run it to see live disk read/write speeds per-process
sudo iotop
```
*Press `q` to exit.*
