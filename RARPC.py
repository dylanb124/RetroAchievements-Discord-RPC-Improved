from colorama import Fore, Style, init
import configparser
from datetime import datetime, timezone
from pprint import pprint
from pypresence import Presence 
import re
import requests
import time
import os.path
import time
import warnings
from allSystems import consoleIcons
import psutil

init(autoreset=True)

def log_with_timestamp(message, color=Fore.RESET):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(color + f"[{timestamp}] {message}")

def getData(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        log_with_timestamp(f"HTTP error occurred: {http_err}", Fore.RED)
    except Exception as err:
        log_with_timestamp(f"Other error occurred: {err}", Fore.RED)
    return None

def getUserProfile(api_key, username):
    data = getData(f"https://retroachievements.org/API/API_GetUserProfile.php?y={api_key}&u={username}")
    if data is None:
        raise ValueError("Failed to fetch user profile data.")
    return data

def getUserRecentlyPlayedGame(api_key, username, number_of_results):
    data = getData(f"https://retroachievements.org/API/API_GetUserRecentlyPlayedGames.php?y={api_key}&u={username}&c={number_of_results}")
    if data is None or len(data) == 0:
        raise ValueError("Failed to fetch recently played game data.")
    return data[0]

def getGameInfoAndUserProgress(api_key, username, game_id):
    data = getData(f"https://retroachievements.org/API/API_GetGameInfoAndUserProgress.php?y={api_key}&u={username}&g={game_id}")
    if data is None:
        raise ValueError("Failed to fetch game info and user progress data.")
    return data

# This function returns a list [totalAchievementsAchieved, totalAchievements]. Both of these are progression type and one win condition achievement.
def getBeatenAchievements(gameInfoAndUserProgress):
    totalProgressionAchievements = 0
    totalWinConditionAchievements = 0
    totalProgressionAchieved = 0
    totalWinConditionAchieved = 0
    winConditionAchieved = 0

    for achievement in gameInfoAndUserProgress['Achievements'].values():
        if(achievement['type'] == "progression"):
            totalProgressionAchievements += 1 # Counts the total number of progression achievements
            if 'DateEarned' in achievement:
                totalProgressionAchieved += 1 # Counts the total number of progression achievements achieved
        elif(achievement['type'] == "win_condition"):
            totalWinConditionAchievements += 1 # Counts the total number of win condition achievements
            if 'DateEarned' in achievement:
                totalWinConditionAchieved += 1 # Counts the total number of win condition achievements achieved

    if totalWinConditionAchieved > 0:
        winConditionAchieved = 1
    else:
        winConditionAchieved = 0

    totalAchievements = totalProgressionAchievements + 1 # Adds 1 since the game is considered beaten if the user have just at least 1 win condition achievement
    totalAchievementsAchieved = totalProgressionAchieved + winConditionAchieved
    
    return [totalAchievementsAchieved, totalAchievements]


def timeDifferenceFromNow(timeStamp):
    current_time = datetime.now(timezone.utc)
    target_time = datetime.strptime(timeStamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    differenceInMinutes = abs((target_time - current_time).total_seconds() / 60)
    return int(differenceInMinutes)

def isDiscordRPCAvailable(RPC):
    try:
        RPC.connect()
        RPC.close()
        log_with_timestamp("Discord RPC is available.", Fore.GREEN)
        return True
    except:
        log_with_timestamp("Discord RPC is not available.", Fore.RED)
        return False

def updatePresence(RPC, userProfile, recentlyPlayedGame, isDisplayUsername, start_time, gameBeatenAchievements):
    button1Link = None
    gameCompletionPercentage = int((recentlyPlayedGame['NumAchieved'] / recentlyPlayedGame['NumPossibleAchievements']) * 100)
    gameBeatenPercentage = int((gameBeatenAchievements[0] / gameBeatenAchievements[1]) * 100)
    largeImageHoverText = f"{recentlyPlayedGame['NumAchieved']} of {recentlyPlayedGame['NumPossibleAchievements']} achieved🏆| {gameCompletionPercentage} %"

    if(isDisplayUsername):
        button1Link = {"label": "Visit Profile 👤", "url": f"https://retroachievements.org/user/{userProfile['User']}"}
    else:
        button1Link = {"label": "What is RetroAchievements❓", "url": "https://retroachievements.org"}
    
    button2Link = {"label": "Game Info 🎮", "url": f"https://retroachievements.org/game/{recentlyPlayedGame['GameID']}"}
    
    try:
        RPC.update(
            details = recentlyPlayedGame['Title'],
            state = f"{userProfile['RichPresenceMsg']} | Story Progress: {gameBeatenPercentage} %",
            start = start_time,
            large_image = f"https://media.retroachievements.org{recentlyPlayedGame['ImageIcon']}",
            large_text = largeImageHoverText,
            small_image = consoleIcons.get(recentlyPlayedGame['ConsoleID']),
            small_text = recentlyPlayedGame['ConsoleName'],
            buttons = [button1Link, button2Link]
        )
    except:
        log_with_timestamp("Failed to update presence.", Fore.RED)
        pass
        

def setup_config():
    config_file = open("config.ini","w")
    usr = ""
    api = ""

    if not os.getenv('RETROACHIEVEMENTS_USERNAME'):
        print(f'Enter RetroAchievements username: ')
        usr = str(input())
    if not os.getenv('RETROACHIEVEMENTS_API_KEY'):
        print(f'Enter RetroAchievements api_key: ')
        api = str(input())

    data = f"""
[DISCORD]
username = {usr}
api_key = {api}

[SETTINGS]
# If set to True, the username will be displayed in the presence. If False, the username won't be displayed.
displayUsername = True

# If set to True, the presence won't timeout unless you stop the script. If False, the presence will timeout after a certain time.
keepRunning = False

# This is the time in minutes after which the presence will be cleared after you quitted playing (if keepRunning is set to False).
# Increase the number if your game device has an unstable internet connection. (This is to prevent the presence from being cleared when you're still playing)
timeoutInMinutes = 5

# This is the time in seconds after which the presence will be updated
refreshRateInSeconds = 15
    """

    config_file.write(data)
    config_file.close()

def main():
    # GLOBAL SET
    isRPCRunning = False

    log_with_timestamp("HOW TO USE:\n1. Open Discord app.\n2. Run this script.\nDiscord app should be running first before this script.\n", Fore.YELLOW)

    if(os.path.exists('config.ini') == False):
        log_with_timestamp("Config file not found. Running first time setup...", Fore.YELLOW)
        setup_config()

    config = configparser.ConfigParser()
    config.read('config.ini')
    
    username = os.getenv('RETROACHIEVEMENTS_USERNAME', config.get('DISCORD', 'username'))
    api_key = os.getenv('RETROACHIEVEMENTS_API_KEY', config.get('DISCORD', 'api_key'))
    isDisplayUsername = config.getboolean('SETTINGS', 'displayUsername')
    keepRunning = config.getboolean('SETTINGS', 'keepRunning')
    timeoutInMinutes = config.getint('SETTINGS', 'timeoutInMinutes')
    refreshRateInSeconds = config.getint('SETTINGS', 'refreshRateInSeconds')

    client_id = os.getenv('DISCORD_CLIENT_ID', "1320752097989234869")

    RPC = Presence(client_id)
    print(Fore.CYAN + "Checking Discord RPC availability...")

    while(isDiscordRPCAvailable(RPC) == False):
        log_with_timestamp("Retrying in 10 seconds...", Fore.RED)
        time.sleep(10)

    time.sleep(5)
    RPC.connect()

    log_with_timestamp("Connected!", Fore.MAGENTA)

    print("Timeout in minutes: ", timeoutInMinutes)
    print("Refresh rate in seconds: ", refreshRateInSeconds)

    start_time = int(time.time())

    while True:
        warnings.filterwarnings("ignore")

        try:
            # For getting the rich presence message
            userProfile = getUserProfile(api_key, username)

            # For getting the recently played game
            recentlyPlayedGame = getUserRecentlyPlayedGame(api_key, username, 1)

            # Getting achievements data
            gameInfoAndUserProgress = getGameInfoAndUserProgress(api_key, username, recentlyPlayedGame['GameID'])
            gameBeatenAchievements = getBeatenAchievements(gameInfoAndUserProgress)

            if(keepRunning == False):
                if(timeDifferenceFromNow(recentlyPlayedGame['LastPlayed']) < timeoutInMinutes):
                    if(isRPCRunning == False):
                        start_time = int(time.time())
                    updatePresence(RPC, userProfile, recentlyPlayedGame, isDisplayUsername, start_time, gameBeatenAchievements)
                    isRPCRunning = True
                else:
                    RPC.clear()
                    isRPCRunning = False
            else:
                updatePresence(RPC, userProfile, recentlyPlayedGame, isDisplayUsername, start_time, gameBeatenAchievements)
        except ValueError as ve:
            log_with_timestamp(f"Value error: {ve}", Fore.RED)
        except Exception as e:
            log_with_timestamp(f"Error during presence update: {e}", Fore.RED)
            isRPCRunning = False
            log_with_timestamp("Rechecking Discord RPC availability...", Fore.CYAN)
            while(isDiscordRPCAvailable(RPC) == False):
                log_with_timestamp("Retrying in 10 seconds...", Fore.RED)
                time.sleep(10)
            RPC.connect()

        time.sleep(refreshRateInSeconds)
        
if __name__ == "__main__":
    main()
