# ShortsForge Server Deployment Guide (V2 Autopilot)

This guide walks you through deploying the V2 Autopilot pipeline to any headless Linux server (e.g., an Oracle Cloud Compute VM). 

The goal of this deployment strategy is to keep the server completely "dumb". All Google authentication and YouTube channel setups are done locally on your Windows PC. You simply bundle the authenticated database and the code into a payload, drop it on the server, and let it run automatically.

---

## Phase 1: Prepare the Deployment Payload (On Windows)

Before touching the cloud server, you need to bundle your code and your pre-authenticated channels.

### 1. Authenticate Channels Locally
Ensure you have run `python scripts/add_channel.py` on your Windows PC for every channel you intend to upload to. This generates the encrypted tokens inside your local `data/shortsforge.db`.

### 2. Configure Scraper Accounts
Open `scripts/scraper/configs/accounts.json` on your Windows PC and ensure your newly added channels are mapped correctly with their target niches. The packager will bundle this file!

### 3. Build the Code Package
Run the automated deployment packager from your project root:
```bash
python scripts/utils/build_v2_autopilot_deployment.py
```
This script will instantly generate a completely clean `deploy.zip` file containing ONLY the V2 pipeline, leaving behind all legacy V1 junk, test files, and bloated dependencies.

### 3. Gather your Secrets
The `deploy.zip` file intentionally strips out your private secrets for safety. You must manually locate the following files on your computer to transfer alongside the zip:
1. `.env` (Your API keys)
2. `data/shortsforge.db` (Your authenticated channels and quotas)
3. `data/credentials/drive_token.json` (Only needed if you use Google Drive backups)
4. `data/credentials/client_secret.json` (Required: acts as the master key. Used automatically by the server to re-authenticate and generate new access tokens whenever your YouTube or Google Drive tokens expire.)

## Phase 2: Create the Network (Crucial Step)

Oracle's "Create Instance" page has a notorious bug with its networking shortcuts. To ensure your server gets a Public IP address so you can connect to it, you must use the Network Wizard *before* creating the server.

1. In the Oracle Cloud Console, open the main menu (top left) and go to **Networking** -> **Virtual Cloud Networks**.
2. Click the big blue **"Start VCN Wizard"** button.
3. Select **"Create VCN with Internet Connectivity"** and hit Start.
4. Name it something like `yt-automation-vcn`.
5. Leave all the default CIDR blocks exactly as they are. 
6. Click **Next** -> **Create**. 

*(This automatically builds a perfect VCN, Public Subnet, and Internet Gateway without any glitches).*

---

## Phase 3: Provision the Server

When creating your Linux Server (Ubuntu 22.04 LTS), you want the server to automatically install Python and FFmpeg on its very first boot so you don't have to type terminal commands.

### Method 1: The Oracle "Cloud-Init" Template (Automated)
1. Go to the **Oracle Cloud Console** -> **Create Compute Instance**.
2. Select **Ubuntu 22.04** as the image.
3. Configure the hardware and storage using these exact settings:
   - **Image / OS**: Ubuntu 22.04 (Do not choose Oracle Linux).
   - **Shape**: `VM.Standard.E4.Flex` (AMD) or `VM.Standard3.Flex` (Intel). 
     > [!TIP]
     > If Oracle throws an "Out of capacity" error for the AMD shape, immediately switch to the Intel `VM.Standard3.Flex` shape. It performs identically and is rarely sold out.
   - **CPU**: `2 OCPUs` (More than enough for sequential FFmpeg rendering).
   - **Memory (RAM)**: `8 GB` to `12 GB` (Economical and safe for Trial credits).
   - **Boot Volume**: Set to `100 GB` with `10 VPU` (Covered by Free Tier).
4. Scroll down to **Advanced Options** -> **Management** -> **Initialization Script**.
   - Select **"Select Cloud-init script file"**.
   - Click **Browse** and upload the `scripts/utils/v2_autopilot_ubuntu_setup.sh` file directly from your Windows PC.
   > [!WARNING]
   > **The "Incorrectly formatted request" Bug:** If Oracle throws this API error when you click Create, it means the script file is incompatible with Oracle's UI validation. Do not use it. Simply leave the Cloud-Init box completely blank, click Create, and we will run the setup script manually in Phase 5!
5. Scroll up to the **Networking** section. 
   - Select **"Select existing virtual cloud network"**.
   - Choose the `yt-automation-vcn` you created in Phase 2.
   - Verify that **"Assign a public IPv4 address"** is selected.
6. Scroll down to the **SSH Keys** section.
   - Select **"Generate a key pair for me"** and download the Private Key (`.key` file). You will need this for WinSCP!
7. Click **Create**.

When the server finishes provisioning, it will automatically install Python 3.13 and FFmpeg in the background and create a `/home/ubuntu/shortsforge` folder for you!

### Method 2: Manual Execution (Alternative/Fail-Safe)
If you forgot to paste the script into the Oracle UI, or if you are using a different host like DigitalOcean where there is no Cloud-Init box, don't worry! 
Because the setup script is bundled inside `deploy.zip`, you can just execute it directly on the server *after* you transfer your files. You will simply run `sudo bash scripts/utils/v2_autopilot_ubuntu_setup.sh` during Phase 5.

---

## Phase 4: Connect & Transfer the Files

Once the server is running, you need to move your payload onto it. We highly recommend using **WinSCP** because it provides a visual file explorer.

### Step 1: Connect via WinSCP
1. Download and install WinSCP: [https://winscp.net/eng/download.php](https://winscp.net/eng/download.php)
2. Open WinSCP and enter your server details:
   - **Host name**: Your server's new Public IP address.
   - **User name**: `ubuntu` (All lowercase).
   - **Password**: *Leave this blank!*
3. Click **Advanced...** -> **SSH** -> **Authentication**.
4. Click the **"..."** browse button next to Private key file, and select the `.key` file you downloaded from Oracle.
   > [!NOTE]
   > **Key Conversion Prompt:** WinSCP will pop up asking to convert your OpenSSH key to PuTTY format. Click **OK**, save the new `.ppk` file right next to your original key, and click OK again. WinSCP will automatically load the new `.ppk` file.
5. Click **OK** on the advanced settings window, and click **Login**!
   *(If a security warning pops up asking if you trust the server, click Yes).*

### Step 2: Upload the Files
Once you are logged in, you will be looking at the `/home/ubuntu` directory.
1. Open the `shortsforge` folder (if it doesn't exist, create it).
2. Drag and drop the `deploy.zip` and `.env` files directly into `/home/ubuntu/shortsforge`.
3. Open the `data/` folder (create it if missing).
4. Drag and drop `shortsforge.db` into the `data/` folder.
5. Create a `credentials/` folder inside `data/`, and drop `drive_token.json` inside it (if you use Google Drive backups).

---

## Phase 5: Final Setup & Cron Job

Now you need to open a terminal connection to your server to execute the final setup.

### Step 1: Open an SSH Terminal
The easiest way is to use WinSCP's built-in terminal:
1. In WinSCP, click the **"Open Terminal"** icon in the top toolbar (it looks like a little black console screen, or press `Ctrl+P`).
2. This will automatically open a PuTTY terminal window securely connected to your server!

*(Alternatively, you can open Windows Terminal / PowerShell and type: `ssh -i "C:\path\to\your\key.key" ubuntu@YOUR_SERVER_IP`)*

### Step 2: Unzip the Code & Install Dependencies
Run these commands one by one in your new terminal window:
```bash
# Go to your project folder
cd ~/shortsforge

# 1. Ensure 'unzip' is installed (in case Cloud-Init failed)
sudo apt-get update && sudo apt-get install -y unzip

# 2. Extract the deployment package
unzip -o deploy.zip
rm deploy.zip

# 3. Run the setup script (installs Python 3.13 & FFmpeg)
sudo bash scripts/utils/v2_autopilot_ubuntu_setup.sh

# 4. Set up Python environment
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r deploy_requirements.txt
playwright install chromium
sudo playwright install-deps chromium

# Tip: If you ever want to exit the virtual environment without closing the terminal, simply type:
# deactivate
```

### Step 3: Run it Overnight (Background Testing)
Before relying on the automatic daily scheduler, you probably want to run it manually overnight so you can wake up and check for any errors. To do this, we will use `tmux` (a tool that keeps your terminal running even after you close your computer).

1. Type `tmux` and press Enter. (This opens a special background terminal).
2. Activate your environment again just to be safe:
   `source .venv/bin/activate`
3. Start the autopilot:
   `python scripts/autopilot.py`
4. **How to disconnect and sleep:** Press `Ctrl + B` on your keyboard, let go, and then press `D` (for Detach). 
5. You can now completely close WinSCP and turn off your Windows PC!

**How to check it tomorrow:**
When you wake up, log back into the server via WinSCP, open the terminal, and type:
`tmux attach`
This will instantly pull up your exact terminal session from last night so you can read all the success/error messages!

**How to clean up (Tomorrow):**
- When you are done looking at the logs and want to completely delete the background `tmux` session, just type `exit` and hit Enter. 
- *(Note: If you ever just want to exit the Python `.venv` sandbox without closing the terminal, the command is simply `deactivate`)*.

---

### Step 4: Schedule the Daily Autopilot (Cron)
Once you have tested it and know it works flawlessly, you can automate it to run every day at 3:00 AM. 
Type the following command to open the scheduler:
```bash
crontab -e
```
*(If prompted to choose an editor, press `1` for nano).*

Add the following line to the very bottom of the file:
```bash
0 3 * * * cd /home/ubuntu/shortsforge && /home/ubuntu/shortsforge/.venv/bin/python scripts/autopilot.py >> /home/ubuntu/shortsforge/data/cron.log 2>&1
```

Save and exit (In nano: `Ctrl+O`, `Enter`, `Ctrl+X`).

**Deployment Complete! 🎉** 
Your server is now a fully automated, headless workhorse. It will wake up every day at 3:00 AM, scrape new stories, render them using the database tokens, upload them to YouTube, and go back to sleep.

---

## Managing Channels Post-Deployment

If you ever need to add a new YouTube channel after the server is already running, you must be careful not to overwrite the server's database with an empty local database, or you will lose track of all generated videos!

Here is the safe way to do it without typing SQL commands on the Linux server:
1. Open WinSCP and **download** the server's `data/shortsforge.db` to your Windows PC (replacing your local copy). This ensures you have the server's active state.
2. Run `python scripts/add_channel.py` on your Windows PC. The browser will pop up, and the new encrypted token will be saved into the downloaded database.
3. Drag that updated `shortsforge.db` back onto the server in WinSCP to overwrite the old one.
4. Finally, right-click `scripts/scraper/configs/accounts.json` on the server in WinSCP, click Edit, and add your new channel's niches there so the scraper knows about it.

