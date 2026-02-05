import gspread

# 1. Connect using your existing credentials
gc = gspread.service_account(filename=r'C:\Users\nikhil kumar\OneDrive\Desktop\lead-prospecting-agent\config\service-account.json')

# 2. Check how many files the bot actually owns
files = gc.list_spreadsheet_files()
print(f"The Service Account currently has {len(files)} files.")

# 3. Delete old files to free up space
print("Starting cleanup...")
for f in files:
    try:
        # Optional: Only delete files with a specific name pattern if you want to be safe
        # if "Agent02_Enriched" in f['name']:
        print(f"Deleting: {f['name']} (ID: {f['id']})")
        gc.del_spreadsheet(f['id'])
    except Exception as e:
        print(f"Error deleting {f['name']}: {e}")

print("Cleanup complete. The Service Account storage is now empty.")