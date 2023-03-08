from pydrive.drive import GoogleDrive
from pydrive.auth import GoogleAuth
import utils.config as Config
import os, datetime


class Drive:
    def backup_dir(path: str = "data"):
        if Config.LoadConfig().get("backup-google-drive", False)==True:
            if not os.path.exists("client_secrets.json"):
                creds = os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDENTIAL')
                f = open('client_secrets.json', 'w')
                f.write(creds)

            gauth = GoogleAuth()
            gauth.LoadCredentialsFile("data/mycreds.txt")

            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()

            gauth.SaveCredentialsFile("data/mycreds.txt") 
            drive = GoogleDrive(gauth)

            for x in os.listdir(path):
                f = drive.CreateFile({'title' : x})
                f.SetContentFile(os.path.join(path,x))
                f.Upload()

                f = None
                print(f"[{datetime.datetime.now()}] Backup succeeded: {x}")
    
    def backup(path: str):
        if Config.LoadConfig().get("backup-google-drive", False)==True:
            if not os.path.exists("client_secrets.json"):
                creds = os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDENTIAL')
                f = open('client_secrets.json', 'w')
                f.write(creds)

            gauth = GoogleAuth()
            gauth.LoadCredentialsFile("data/mycreds.txt")

            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()

            gauth.SaveCredentialsFile("data/mycreds.txt") 
            drive = GoogleDrive(gauth)

            f = drive.CreateFile({'title' : os.path.basename(path)})
            f.SetContentFile(path)
            f.Upload()

            f = None
            print(f"[{datetime.datetime.now()}] Backup succeeded: {path}")

    def download_dir(path: str = "data"):
        if Config.LoadConfig().get("backup-google-drive", False)==True:
            if not os.path.exists("client_secrets.json"):
                creds = os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDENTIAL')
                f = open('client_secrets.json', 'w')
                f.write(creds)

            gauth = GoogleAuth()
            gauth.LoadCredentialsFile("data/mycreds.txt")

            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()

            gauth.SaveCredentialsFile("data/mycreds.txt") 
            drive = GoogleDrive(gauth)
            
            for x in os.listdir(path):
                try:
                    file_id = drive.ListFile({'q': f'title = "{os.path.basename(x)}"'}).GetList()[0]['id']

                    f = drive.CreateFile({'id': file_id})
                    f.GetContentFile(f"data/{os.path.basename(x)}")
                    
                    print(f"[{datetime.datetime.now()}] Download succeeded: {x}")
                except Exception as e:
                    pass
    
    def download(path: str):
        if Config.LoadConfig().get("backup-google-drive", False)==True:
            if not os.path.exists("client_secrets.json"):
                creds = os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDENTIAL')
                f = open('client_secrets.json', 'w')
                f.write(creds)
                
            gauth = GoogleAuth()
            gauth.LoadCredentialsFile("data/mycreds.txt")

            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()

            gauth.SaveCredentialsFile("data/mycreds.txt") 
            drive = GoogleDrive(gauth)
            
            try:
                file_id = drive.ListFile({'q': f'title = "{os.path.basename(path)}"'}).GetList()[0]['id']

                f = drive.CreateFile({'id': file_id})
                f.GetContentFile(f"{path}")
                    
                print(f"[{datetime.datetime.now()}] Download succeeded: {path}")
            except Exception as e:
                pass
            