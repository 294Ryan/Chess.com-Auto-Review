<!---------------- LINKS_START -------------------->

[release_badge]: https://img.shields.io/github/release/294Ryan/Chess.com-Auto-Review?color=red&label=Release&style=flat-square
[star_badge]: https://img.shields.io/endpoint?color=yellow&url=https://api.pinstudios.net/api/badges/stars/294Ryan/Chess.com-Auto-Review&style=flat-square
[license_badge]: https://img.shields.io/badge/License-MIT-orange?color=orange&style=flat-square
[os_badge]: https://img.shields.io/badge/Supported-Windows_10+-blue?style=flat-square
[contributors_badge]: https://contrib.rocks/image?repo=294Ryan/Chess.com-Auto-Review

[last_release]: https://github.com/294Ryan/Chess.com-Auto-Review/releases/latest
[release]: https://github.com/294Ryan/Chess.com-Auto-Review/releases
[star]: https://github.com/294Ryan/Chess.com-Auto-Review/stargazers
[license]: https://github.com/294Ryan/Chess.com-Auto-Review/blob/main/LICENSE
[contributors]: https://github.com/294Ryan/Chess.com-Auto-Review/graphs/contributors

<!----------------- LINKS_END --------------------->

<div align='center'>
  <br>
  <h1><b>Chess.com-Auto-Review</b></h1>
  <h3>Batch-run Chess.com Game Review on your entire game history</h3>

  ![Python](https://img.shields.io/badge/python-%233670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
  ![Selenium](https://img.shields.io/badge/-selenium-%43B02A?style=for-the-badge&logo=selenium&logoColor=white)
  <br>

  [![Release][release_badge]][last_release]
  [![Stars][star_badge]][star]
  [![License][license_badge]][license]
  ![Supported OS][os_badge]
  <br>

  [Quick Start](#quick-start) | [Usage](#usage) | [Features](#features) | [Limitations](#limitations) | [License](#license) | [Contributors](#contributors)

</div>

---

## **Quick Start**

> [!NOTE]
> System Requirements:  
> Windows 10 or above  
> Google Chrome installed  
> A Chess.com premium account with the interface language set to English  
> Python 3 (tested with 3.10), required only when running from source  

- **Direct Download (Recommended)**: Go to [Release][release], download `Chess.com-Auto-Review.exe`, and run it.
- **Run from Source**:
  ```
  git clone https://github.com/294Ryan/Chess.com-Auto-Review.git
  cd Chess.com-Auto-Review
  pip install selenium
  python main.py
  ```

---

## **Usage**

1. Enter your **Chess.com username** and the **number of tabs** to analyze at once (1-20, recommended 5).
2. A dedicated Chrome window opens. On the first run, **log in to Chess.com** in that window, then press **Enter** in the console. The login is kept in the dedicated profile.
3. The tool fetches your games through the Chess.com public API and opens their review pages **from newest to oldest**. Each tab is closed once the `Start Review` button appears. The results stay on Chess.com.
4. Press **Ctrl+C** to stop. On the next run, unfinished games and games that failed or timed out (600 seconds) are queued again, and games already marked `done` are skipped.

**Data and logs** are stored in `%APPDATA%\Chess.com-Auto-Review\`:

- `chromeProfile\`: the dedicated Chrome profile (contains your Chess.com login session)
- `progress.db`: SQLite progress database
- `logs\`: one log file per launch, named `YYYY-MM-DD-HH-MM-SS-mmm.log`, containing normal output and errors

---

## **Features**
- **Full-history batch review**: Collects every game from the public API and triggers the native Game Review, newest first.
- **Multi-tab analysis**: Runs 1-20 review tabs at the same time, polled from a single thread.
- **Resumable progress**: Tracks each game as `pending`, `running`, `done`, or `failed` in SQLite, so interrupted runs continue where they stopped.
- **Self-recovery**: Re-queues games whose tab was closed manually and reconnects automatically if ChromeDriver stops responding while Chrome is still open.
- **Per-launch logs**: Every run writes a separate, timestamped log file.
- **Login-friendly browser**: Starts a regular Chrome with a dedicated profile and attaches Selenium to it, which avoids sign-in blocks on automated browsers.

---

## **Limitations**
- **Windows and English interface only**: Completion detection looks for the English `Start Review` button text.
- **Completion detection depends on the page**: A Chess.com layout change can break it.
- **Single Chrome, single thread**: Tabs are polled one after another, not processed in parallel threads.
- **Tabs must stay open** until the analysis finishes. Do not close them manually (a closed tab is re-queued).
- **Fixed debugging port (9222)**: The tool attaches to whatever Chrome is already listening on port 9222. Close any other Chrome started with remote debugging before running.
- **Internet access required**: Chess.com API access, plus Selenium resolving a matching ChromeDriver.
- **Results are not exported**: They remain on Chess.com.
- **Not affiliated with Chess.com**: Users are responsible for following the Chess.com Terms of Service and their membership limits.

---

## **License**
License: [MIT License][license]
> [!WARNING]
> Please use the contents of this project within the scope permitted by the license. Users are solely responsible for any consequences resulting from improper or negligent use.

---

## **Contributors**
[![Contributors][contributors_badge]][contributors]

<br><br>
<div align="center">
  <a href="#top">Back to top</a>
</div>
