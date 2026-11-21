import os
import json
import time
import socket
import shutil
import sqlite3
import subprocess
import traceback
import urllib.request
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By

dataDir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Chess.com-Auto-Review")    # %APPDATA%\Chess.com-Auto-Review
profileDir = os.path.join(dataDir, "chromeProfile")
dbPath = os.path.join(dataDir, "progress.db")
logDir = os.path.join(dataDir, "logs")
logPath = None    # set by initLog()
maxTabs = 5    # default, overwritten by user input at startup
reviewTimeout = 600    # max wait per game (seconds)
pollInterval = 2    # polling interval (seconds)
debugPort = 9222    # Chrome remote debugging port
maxReconnect = 10    # max driver reconnects per run

class DriverLostError(Exception):
    pass    # raised once the driver is confirmed dead so the main loop can recover right away

def initLog():
    global logPath
    os.makedirs(logDir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]    # millisecond precision
    suffix = 0
    while True:
        path = os.path.join(logDir, f"{stamp}{'-' + str(suffix) if suffix else ''}.log")
        try:
            open(path, "x", encoding="utf-8").close()    # exclusive create, never reuses another run's file
            break
        except FileExistsError:
            suffix += 1
    logPath = path

def writeLog(text):
    if logPath is None:
        return
    with open(logPath, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")

def log(msg):
    print(msg)
    writeLog(msg)

def logError(msg):
    print(msg, "(see log file for details)")
    writeLog(f"ERROR {msg}\n{traceback.format_exc()}")    # call only inside an except block

def findChrome():
    parts = ["Google", "Chrome", "Application", "chrome.exe"]
    for envName in ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"]:
        path = os.path.join(os.environ.get(envName, ""), *parts)
        if os.path.exists(path):
            return path
    return shutil.which("chrome")

def isPortOpen():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", debugPort)) == 0

def launchChrome():
    if isPortOpen():
        return    # Chrome is already listening, connect to it
    chromePath = findChrome()
    if chromePath is None:
        log("Chrome not found. Please make sure it is installed")
        raise SystemExit(1)
    subprocess.Popen([
        chromePath,
        f"--remote-debugging-port={debugPort}",
        f"--user-data-dir={profileDir}",
        "--disable-background-timer-throttling",    # keep background tabs from being throttled
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ])
    for _ in range(30):
        if isPortOpen():
            return
        time.sleep(0.5)
    log(f"Chrome did not start on port {debugPort}. If a Chrome using the same profile is already open, close all its windows first")
    raise SystemExit(1)

def connectDriver():
    options = webdriver.ChromeOptions()
    options.debugger_address = f"127.0.0.1:{debugPort}"    # attach to the normally launched Chrome
    options.page_load_strategy = "eager"    # do not wait for every resource, avoids stalls when opening tabs
    return webdriver.Chrome(options=options)

def fetchJson(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Chess.com-Auto-Review/1.0.0"})    # the API requires a User-Agent
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)

def openDb():
    db = sqlite3.connect(dbPath)
    db.execute("CREATE TABLE IF NOT EXISTS games (gameKey TEXT PRIMARY KEY, reviewUrl TEXT, endTime INTEGER, status TEXT, updatedAt REAL)")
    db.execute("UPDATE games SET status='pending' WHERE status IN ('running', 'failed')")    # re-queue games left running or failed by a previous run
    db.commit()
    return db

def syncGames(db, userName):
    archives = fetchJson(f"https://api.chess.com/pub/player/{userName}/games/archives")["archives"]
    for archiveUrl in archives:
        for g in fetchJson(archiveUrl)["games"]:
            if "/game/" not in g.get("url", ""):
                continue
            gameKey = g["url"].split("/game/")[1]    # e.g. live/123456
            reviewUrl = f"https://www.chess.com/analysis/game/{gameKey}/review"
            db.execute("INSERT OR IGNORE INTO games VALUES (?, ?, ?, 'pending', ?)", (gameKey, reviewUrl, g.get("end_time", 0), time.time()))    # existing games are not overwritten
    db.commit()

def setStatus(db, gameKey, status):
    db.execute("UPDATE games SET status=?, updatedAt=? WHERE gameKey=?", (status, time.time(), gameKey))
    db.commit()

def getNextPending(db):
    return db.execute("SELECT gameKey, reviewUrl FROM games WHERE status='pending' ORDER BY endTime DESC LIMIT 1").fetchone()    # newest first

def getCounts(db):
    return dict(db.execute("SELECT status, COUNT(*) FROM games GROUP BY status").fetchall())

def findVisible(driver, text):
    xpath = f"//*[self::button or self::a][normalize-space()='{text}']"
    for el in driver.find_elements(By.XPATH, xpath):
        if el.is_displayed():
            return el
    return None

def isDriverProcessDead(driver):
    process = getattr(getattr(driver, "service", None), "process", None)
    return process is not None and process.poll() is not None    # ChromeDriver exited; avoids slow connection-refused retries

def isBrowserAlive(driver):
    if isDriverProcessDead(driver):
        return False
    for i in range(3):
        try:
            return len(driver.window_handles) > 0
        except Exception:
            if i == 2:
                logError(f"Driver unresponsive (Chrome port open: {isPortOpen()})")    # logged after 3 consecutive failures
            time.sleep(1)
    return False

def reconnect(driver):
    try:
        driver.service.stop()    # stops ChromeDriver only, Chrome is not affected
    except Exception:
        pass    # old driver is already dead
    driver = connectDriver()
    handles = driver.window_handles
    for handle in handles[1:]:
        closeTab(driver, handle)    # close leftover review tabs, their games are re-queued
    driver.switch_to.window(handles[0])
    driver.get("https://www.chess.com/home")
    return driver, handles[0]

def switchToMain(driver, mainHandle):
    handles = driver.window_handles
    driver.switch_to.window(mainHandle if mainHandle in handles else handles[0])    # fall back to another tab if the main tab was closed

def closeTab(driver, handle):
    try:
        driver.switch_to.window(handle)
        driver.close()
    except Exception:
        pass    # tab already gone

def openGame(driver, db, active, gameKey, reviewUrl):
    setStatus(db, gameKey, "running")
    try:
        driver.switch_to.new_window("tab")
        active[driver.current_window_handle] = (gameKey, time.time())    # register first so a failed get is still cleaned up by the timeout
        driver.get(reviewUrl)
        return True
    except Exception:
        logError(f"Failed to open {gameKey}")
        alive = isBrowserAlive(driver)
        if gameKey not in [v[0] for v in active.values()]:
            setStatus(db, gameKey, "failed" if alive else "pending")    # not a failure if the browser is gone
        if not alive:
            raise DriverLostError("Driver is unresponsive")    # stop the round and let the main loop recover
        return False

def getTabState(driver, handle, startTime):
    try:
        if handle not in driver.window_handles:
            return "closed"    # the user closed the tab manually
        driver.switch_to.window(handle)
        if findVisible(driver, "Start Review"):    # Start Review appearing means the analysis is complete
            return "done"
    except Exception:
        logError("Tab check error")
        if not isBrowserAlive(driver):
            raise DriverLostError("Driver is unresponsive")    # stop the round and let the main loop recover
        return "failed"
    if time.time() - startTime > reviewTimeout:
        return "failed"
    return "running"

def runRound(driver, db, active, mainHandle):
    if isDriverProcessDead(driver):
        raise DriverLostError("ChromeDriver process has exited")    # fast path, no slow retries

    ### Fill Tabs ###
    while len(active) < maxTabs:
        row = getNextPending(db)
        if row is None:
            break
        if not openGame(driver, db, active, row[0], row[1]):
            break    # opening failed: poll first, retry next round
    if not active and getNextPending(db) is None:
        return False

    ### Poll Tabs ###
    for handle in list(active):
        gameKey, startTime = active[handle]
        state = getTabState(driver, handle, startTime)
        if state == "running":
            continue
        del active[handle]
        if state == "closed":
            setStatus(db, gameKey, "pending")    # tab was closed, re-queue
            log(f"{gameKey} tab was closed, re-queued")
        else:
            setStatus(db, gameKey, state)
            closeTab(driver, handle)
            log(f"{gameKey} {state} ({time.time() - startTime:.0f}s) {getCounts(db)}")
        switchToMain(driver, mainHandle)
    return True

def main():
    global maxTabs
    initLog()
    log(f"Log file: {logPath}")
    userName = input("Enter your Chess.com username: ").strip()
    while True:
        value = input("Enter the number of tabs to analyze at once (1-20, recommended 5): ").strip()
        if value.isdigit() and 1 <= int(value) <= 20:
            maxTabs = int(value)
            break
        log("Please enter an integer between 1 and 20")
    log(f"Username: {userName}, tabs: {maxTabs}")

    ### Launch Browser ###
    launchChrome()
    driver = connectDriver()
    mainHandle = driver.current_window_handle    # keep this tab open
    driver.get("https://www.chess.com/home")
    input("Log in to Chess.com in the opened Chrome window (premium account), then press Enter...")

    ### Prepare Queue ###
    db = openDb()
    log("Fetching game list...")
    syncGames(db, userName)
    log(f"Game status: {getCounts(db)}")

    ### Review Loop ###
    active = {}    # handle -> (gameKey, startTime)
    reconnectCount = 0    # driver reconnects so far in this run
    try:
        while True:
            driverLost = False
            try:
                if not runRound(driver, db, active, mainHandle):
                    log(f"All games processed: {getCounts(db)}")
                    break
            except DriverLostError as e:
                log(f"Driver lost: {e}")
                driverLost = True    # already confirmed, skip probing again
            except Exception:
                logError("Main loop error")
            if driverLost or not isBrowserAlive(driver):
                if not isPortOpen():
                    log("Chrome was closed. Exiting (unfinished games resume next run)")
                    break
                reconnectCount += 1
                if reconnectCount > maxReconnect:
                    log(f"Reached the reconnect limit ({maxReconnect}). Exiting (unfinished games resume next run)")
                    break
                log(f"Chrome is still running but the driver failed. Reconnecting ({reconnectCount}/{maxReconnect})")
                for gameKey, _ in active.values():
                    setStatus(db, gameKey, "pending")    # old tabs get closed, re-queue their games
                active.clear()
                try:
                    driver, mainHandle = reconnect(driver)
                except Exception:
                    logError("Reconnect failed")
            time.sleep(pollInterval)
    except KeyboardInterrupt:
        print()
        log("Interrupted. The next run resumes unfinished games")
    finally:
        db.close()
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logError("Fatal error")
        raise    # also show the traceback in the console
