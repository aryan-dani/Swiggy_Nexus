#Requires -Version 5.1
<#
.SYNOPSIS
  Dual-monitor teleprompter for the TWO-beat Swiggy Nexus live demo.

.DESCRIPTION
  Stage 0 cold open, then one step card at a time with CLICK + SPEAK
  on the same screen. Guides docs/demo-script.md beat choreography.

  Usage (API + UI already running):
    .\run-demo-record.ps1
    .\run-demo-record.ps1 -SkipPreflight
    .\run-demo-record.ps1 -Scene 2
    .\run-demo-record.ps1 -ListOnly
    .\run-demo-record.ps1 -SpeakWaitSec 10 -ToolWaitSec 25

.PARAMETER SkipPreflight
  Skip scripts/demo_preflight.py (fast path when stack is already warm).

.PARAMETER Scene
  Start at this beat number (1-2).

.PARAMETER ListOnly
  Print the step outline and exit (no interactive pauses).

.PARAMETER SpeakWaitSec
  Soft countdown after SPEAK/VOICE cards (default 10). ENTER advances early.

.PARAMETER ToolWaitSec
  Soft countdown on WAIT tool-run cards (default 25). ENTER advances early.
#>
[CmdletBinding()]
param(
    [switch]$SkipPreflight,
    [int]$Scene = 1,
    [switch]$ListOnly,
    [int]$SpeakWaitSec = 10,
    [int]$ToolWaitSec = 25
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ApiBase = "http://127.0.0.1:8000"
$UiBase = "http://127.0.0.1:3000"

# Exact voice line for Beat 2 (ASCII dashes; intent matcher ignores punctuation)
$NightOutVoice = "Plan a night out with friends this Saturday -- dinner then drinks, then split the bill"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Hr([string]$Color = "DarkGray") {
    Write-Host ("-" * 72) -ForegroundColor $Color
}

function Write-CueLine([string]$Kind, [string]$Text, [switch]$Large) {
    $c = switch ($Kind) {
        "CLICK" { "Yellow" }
        "SPEAK" { "Green" }
        "VOICE" { "Green" }
        "WAIT"  { "Magenta" }
        "LOOK"  { "Cyan" }
        "POINT" { "Cyan" }
        "DON'T" { "Red" }
        "TIP"   { "DarkYellow" }
        "PANIC" { "DarkYellow" }
        default { "White" }
    }
    $label = ("{0,-5}" -f $Kind)
    Write-Host ("  {0}  >>>  " -f $label) -ForegroundColor $c -NoNewline
    if ($Large -and ($Kind -eq "SPEAK" -or $Kind -eq "VOICE")) {
        Write-Host ""
        Write-Host ""
        Write-Host ("           ""{0}""" -f $Text) -ForegroundColor $c
        Write-Host ""
    } else {
        Write-Host $Text -ForegroundColor White
    }
}

function Show-Header([int]$Beat, [int]$Step, [int]$Total, [string]$ElapsedHint) {
    Clear-Host
    Write-Host ""
    Write-Host ("  BEAT {0} / STEP {1} of {2}" -f $Beat, $Step, $Total) -NoNewline -ForegroundColor White
    if ($ElapsedHint) {
        Write-Host ("          [{0}]" -f $ElapsedHint) -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
    Write-Host "  LEFT=product (camera)     RIGHT=you (teleprompter + Telegram)" -ForegroundColor DarkCyan
    Write-Hr
}

function Wait-Enter([string]$Prompt = "[ENTER] next") {
    Write-Host ""
    Write-Host ("  {0}   [Q] quit" -f $Prompt) -ForegroundColor DarkGray
    while ($true) {
        $line = Read-Host
        if ($null -eq $line) { return "enter" }
        $t = $line.Trim().ToUpperInvariant()
        if ($t -eq "Q") { return "quit" }
        if ($t -eq "S") { return "skip" }
        return "enter"
    }
}

function Wait-Countdown {
    param(
        [int]$Seconds,
        [string]$Label = "speaking / waiting",
        [switch]$AllowSkip
    )
    if ($Seconds -le 0) {
        return (Wait-Enter "[ENTER] next")
    }

    Write-Host ""
    Write-Host ("  Countdown ~{0}s ({1}) -- ENTER advances early" -f $Seconds, $Label) -ForegroundColor DarkGray
    if ($AllowSkip) {
        Write-Host "  [ENTER] next   [S] skip speak wait   [Q] quit" -ForegroundColor DarkGray
    } else {
        Write-Host "  [ENTER] next   [Q] quit" -ForegroundColor DarkGray
    }

    $useConsole = $true
    try { $null = [Console]::KeyAvailable } catch { $useConsole = $false }

    if (-not $useConsole) {
        # Host cannot poll keys -- fall back to blocking Enter
        return (Wait-Enter "[ENTER] when ready (countdown unavailable in this host)")
    }

    $end = (Get-Date).AddSeconds($Seconds)
    $lastShown = -1
    while ((Get-Date) -lt $end) {
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq "Enter") { return "enter" }
            if ($key.Key -eq "Q") { return "quit" }
            if ($AllowSkip -and ($key.Key -eq "S")) { return "skip" }
        }
        $left = [int][Math]::Ceiling(($end - (Get-Date)).TotalSeconds)
        if ($left -lt 0) { $left = 0 }
        if ($left -ne $lastShown) {
            Write-Host ("`r  >>> {0,3}s remaining...   " -f $left) -NoNewline -ForegroundColor Magenta
            $lastShown = $left
        }
        Start-Sleep -Milliseconds 150
    }
    Write-Host ""
    return "enter"
}

function Show-StepCard {
    param(
        [hashtable]$Step,
        [int]$Beat,
        [int]$Index,
        [int]$Total
    )

    $hint = $Step.Hint
    if (-not $hint) { $hint = "" }
    Show-Header -Beat $Beat -Step $Index -Total $Total -ElapsedHint $hint

    if ($Step.Click) { Write-CueLine "CLICK" $Step.Click }
    if ($Step.Speak) { Write-CueLine "SPEAK" $Step.Speak -Large }
    if ($Step.Voice) { Write-CueLine "VOICE" $Step.Voice -Large }
    if ($Step.Wait)  { Write-CueLine "WAIT"  $Step.Wait }
    if ($Step.Look)  { Write-CueLine "LOOK"  $Step.Look }
    if ($Step.Point) { Write-CueLine "POINT" $Step.Point }
    if ($Step.Dont)  { Write-CueLine "DON'T" $Step.Dont }
    if ($Step.Tip)   { Write-CueLine "TIP"   $Step.Tip }
    if ($Step.Panic) { Write-CueLine "PANIC" $Step.Panic }

    Write-Hr
}

function Invoke-StepAdvance {
    param([hashtable]$Step)

    $mode = $Step.Advance
    if (-not $mode) { $mode = "enter" }

    switch ($mode) {
        "enter" {
            return (Wait-Enter "[ENTER] when ready for next (after you click / speak)")
        }
        "confirm" {
            # Never auto-advance past Confirm / Approve clicks
            return (Wait-Enter "[ENTER] AFTER you clicked Confirm / Approve in the UI")
        }
        "speak" {
            $sec = $SpeakWaitSec
            if ($Step.WaitSec) { $sec = [int]$Step.WaitSec }
            return (Wait-Countdown -Seconds $sec -Label "speak pace" -AllowSkip)
        }
        "wait" {
            $sec = $ToolWaitSec
            if ($Step.WaitSec) { $sec = [int]$Step.WaitSec }
            Write-Host ""
            Write-Host "  [ENTER] when tools finish / when you're done speaking" -ForegroundColor DarkGray
            return (Wait-Countdown -Seconds $sec -Label "tool run" -AllowSkip)
        }
        "voice" {
            $sec = [Math]::Max($SpeakWaitSec, 12)
            if ($Step.WaitSec) { $sec = [int]$Step.WaitSec }
            return (Wait-Countdown -Seconds $sec -Label "voice hold+release" -AllowSkip)
        }
        default {
            return (Wait-Enter)
        }
    }
}

# ---------------------------------------------------------------------------
# Beat choreography (matches docs/demo-script.md)
# ---------------------------------------------------------------------------

$beats = @(
    @{
        N = 1
        Title = "Web -- 60s WOW / Chrono-Host + Confirm"
        Mins = "~90s"
        Steps = @(
            @{
                Title = "Intro -- point at Nexus"
                Speak = "This is Swiggy Nexus. One agent across dine-out, Instamart, and food -- staged until I confirm."
                Look  = "LEFT monitor Chat hero + empty Activity rail"
                Point = "Nexus Chat on LEFT (camera sees this)"
                Dont  = "Do not click WOW yet -- speak first"
                Advance = "speak"
                Hint = "speak ~$SpeakWaitSec`s"
            },
            @{
                Title = "Click WOW"
                Click = "Run 60s WOW demo (purple card on Chat hero)"
                Speak = "Watch this."
                Dont  = "type the prompt yourself -- do not click Deadlock / Flow-state / Settings"
                Advance = "enter"
                Hint = "click then ENTER"
            },
            @{
                Title = "Tools fan out"
                Wait  = "Chrono-Host bundle on Activity rail (not 'ran out of tool steps')"
                Speak = "One sentence -- plan my evening -- and Chrono-Host fans out across three Swiggy verticals. Dineout for the table. Instamart for party supplies. Food for dessert. Every chip you see is a real MCP tool call."
                Look  = "LEFT monitor Activity / tool chips"
                Panic = "FAIL: + NEW CHAT -> Run 60s WOW demo again"
                Advance = "wait"
                Hint = "wait ~$ToolWaitSec`s / ENTER early"
            },
            @{
                Title = "Staged -- not spent"
                Point = "RIGHT side of LEFT monitor = Activity / Chrono-Host bundle"
                Speak = "Everything on the right is staged. Nothing is booked. Nothing is checked out."
                Look  = "LEFT Activity Chrono-Host bundle"
                Advance = "speak"
                Hint = "speak ~$SpeakWaitSec`s"
            },
            @{
                Title = "Confirm table"
                Click = "Confirm table (Chrono-Host / Activity panel)"
                Look  = "LEFT Activity Confirm buttons"
                Tip   = "If asked for time: type 8:00 -> Send, then confirm"
                Dont  = "auto-advance -- you must click, then ENTER"
                Advance = "confirm"
                Hint = "CLICK then ENTER"
            },
            @{
                Title = "Confirm groceries"
                Click = "Confirm groceries"
                Look  = "LEFT Activity"
                Advance = "confirm"
                Hint = "CLICK then ENTER"
            },
            @{
                Title = "Confirm dessert + close Beat 1"
                Click = "Confirm dessert"
                Speak = "And only now -- after my explicit confirm -- do the write tools fire. The model stages. The human spends."
                Look  = "LEFT Activity write tools firing"
                Panic = "FAIL: New Chat -> Run 60s WOW demo again"
                Advance = "confirm"
                Hint = "CLICK + speak, then ENTER"
            }
        )
    },
    @{
        N = 2
        Title = "Telegram voice -- Night Out NL"
        Mins = "~60-90s"
        Steps = @(
            @{
                Title = "Switch LEFT to Concierge"
                Click = "LEFT sidebar -> Concierge -> Agent activity (camera stays on LEFT)"
                Look  = "LEFT = Concierge Ops timeline"
                Dont  = "run Night out wizard / /nightout -- stay off slash commands"
                Advance = "enter"
                Hint = "CLICK then ENTER"
            },
            @{
                Title = "Bridge to phone"
                Speak = "Same brain on my phone. One natural sentence -- voice, not a slash command -- and Night Out stages Calendar, a table, and an equal bill split."
                Look  = "Camera / audience -- glance RIGHT for next line"
                Advance = "speak"
                Hint = "speak ~$SpeakWaitSec`s"
            },
            @{
                Title = "Telegram VOICE"
                Voice = $NightOutVoice
                Click = "Telegram mic -> HOLD -> say the line -> RELEASE"
                Dont  = "spam the mic -- one clean hold/release"
                Tip   = "MIC FAIL: TYPE the same sentence (no slash) -> Approve"
                Advance = "voice"
                Hint = "voice ~12s+"
            },
            @{
                Title = "Wait for Approve buttons"
                Wait  = "Transcript -> Planning night out -> Approve / Reject (NOT stuck on Thinking)"
                Speak = "Night Out is the full social loop -- Taste Vault guests, preferred venue, Calendar invite, table booking on the mock MCP, equal UPI split. Still waiting on my Approve."
                Look  = "RIGHT Telegram card + LEFT Ops timeline"
                Panic = "No Approve in 5s? Type the sentence once. Stuck on Thinking? Check API :8000 -- do not re-spam mic."
                Advance = "wait"
                Hint = "wait ~$ToolWaitSec`s / ENTER early"
            },
            @{
                Title = "Approve"
                Click = "Telegram -> Approve (primary). Alt: RIGHT browser Ops -> Approve"
                Dont  = "auto-advance -- click Approve, then ENTER"
                Advance = "confirm"
                Hint = "CLICK then ENTER"
            },
            @{
                Title = "Receipt + bow"
                Wait  = "Ops night_out_receipt -- Calendar / Maps / UPI"
                Speak = "One approve -- Calendar for the group, Maps for the cab, equal split so nobody chases Venmo. Demo UPI handles -- no real collection -- but the math and the links are real. Thank you."
                Look  = "LEFT Ops header + receipt -- STOP RECORDING on this frame"
                Click = "STOP RECORDING -- end on Ops header + receipt"
                Panic = "No receipt? Check Ops pending HITL / API health"
                Advance = "speak"
                Hint = "bow / stop record"
            }
        )
    }
)

# ---------------------------------------------------------------------------
# ListOnly
# ---------------------------------------------------------------------------

function Show-Outline {
    Write-Host ""
    Write-Host "SWIGGY NEXUS -- LIVE DEMO (outline)" -ForegroundColor Magenta
    Write-Hr
    Write-Host "  Voice line: $NightOutVoice" -ForegroundColor DarkGray
    Write-Host ""
    $n = 0
    foreach ($b in $beats) {
        Write-Host ("  BEAT {0}: {1}  ({2})" -f $b.N, $b.Title, $b.Mins) -ForegroundColor Cyan
        $i = 0
        foreach ($s in $b.Steps) {
            $i++
            $n++
            $bits = @()
            if ($s.Click) { $bits += "CLICK" }
            if ($s.Speak) { $bits += "SPEAK" }
            if ($s.Voice) { $bits += "VOICE" }
            if ($s.Wait)  { $bits += "WAIT" }
            if ($s.Point) { $bits += "POINT" }
            $cue = ($bits -join "+")
            if (-not $cue) { $cue = "STEP" }
            Write-Host ("    {0,2}. [{1,-11}] {2}" -f $i, $cue, $s.Title) -ForegroundColor White
        }
        Write-Host ""
    }
    Write-Host ("  Total interactive steps: {0}" -f $n) -ForegroundColor Green
    Write-Host "  Full script: docs\demo-script.md" -ForegroundColor DarkGray
}

if ($ListOnly) {
    Show-Outline
    exit 0
}

if ($Scene -lt 1 -or $Scene -gt $beats.Count) {
    throw "Scene must be 1..$($beats.Count)"
}

if ($SpeakWaitSec -lt 0) { $SpeakWaitSec = 0 }
if ($ToolWaitSec -lt 0) { $ToolWaitSec = 0 }

# ---------------------------------------------------------------------------
# Stage 0 -- cold open (do NOT dump into WOW)
# ---------------------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Magenta
Write-Host "       SWIGGY NEXUS -- LIVE DEMO" -ForegroundColor Magenta
Write-Host "  ============================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  CHECKLIST" -ForegroundColor White
Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  LEFT   = browser Chat fullscreen  ($UiBase)" -ForegroundColor Cyan
Write-Host "  RIGHT  = this window + Telegram Desktop (or phone)" -ForegroundColor Cyan
Write-Host "  Camera = LEFT only (audience never sees notes)" -ForegroundColor Cyan
Write-Host "  Dev mode OFF | Chat tab | reject leftover HITLs | New Chat if dirty" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  TWO BEATS" -ForegroundColor White
Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Beat 1  Web Chrono-Host + Confirm          (~90s)" -ForegroundColor Yellow
Write-Host "  Beat 2  Telegram voice Night Out           (~60-90s)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Doc: $Root\docs\demo-script.md" -ForegroundColor DarkGray
Write-Host "  API: $ApiBase   UI: $UiBase" -ForegroundColor DarkGray
Write-Host ""

# Quiet smoke-check (no long noisy banner)
try {
    $null = Invoke-WebRequest -Uri "$ApiBase/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "  OK  API healthy" -ForegroundColor Green
} catch {
    Write-Host "  !!  API not reachable -- run .\start-local.ps1 first" -ForegroundColor Yellow
}
try {
    $null = Invoke-WebRequest -Uri $UiBase -UseBasicParsing -TimeoutSec 3
    Write-Host "  OK  UI reachable" -ForegroundColor Green
} catch {
    Write-Host "  !!  UI not reachable at $UiBase" -ForegroundColor Yellow
}

if (-not $SkipPreflight) {
    Write-Host ""
    Write-Host "  Preflight (use -SkipPreflight to skip)..." -ForegroundColor DarkGray
    $py = Join-Path $Root "backend\.venv\Scripts\python.exe"
    $pre = Join-Path $Root "scripts\demo_preflight.py"
    if ((Test-Path $py) -and (Test-Path $pre)) {
        & $py $pre
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Preflight reported failures. Fix them, or re-run with -SkipPreflight." -ForegroundColor Yellow
            $r = Wait-Enter "Press ENTER to continue anyway (or Q / Ctrl+C to abort)"
            if ($r -eq "quit") { exit 1 }
        }
    } else {
        Write-Host "  !!  demo_preflight.py / venv python not found -- skipping" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Preflight skipped (-SkipPreflight)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Hr "Yellow"
Write-Host "  Starting Beat $Scene" -ForegroundColor Yellow
$go = Wait-Enter "Press ENTER when camera is rolling and both monitors ready"
if ($go -eq "quit") { exit 0 }

# ---------------------------------------------------------------------------
# Interactive step loop
# ---------------------------------------------------------------------------

$totalAll = 0
foreach ($b in $beats) { $totalAll += $b.Steps.Count }

foreach ($b in $beats) {
    if ($b.N -lt $Scene) { continue }

    $stepCount = $b.Steps.Count
    $idx = 0
    foreach ($s in $b.Steps) {
        $idx++
        Show-StepCard -Step $s -Beat $b.N -Index $idx -Total $stepCount
        Write-Host ("  {0}" -f $s.Title) -ForegroundColor DarkGray
        $action = Invoke-StepAdvance -Step $s
        if ($action -eq "quit") {
            Write-Host ""
            Write-Host "  Quit. Stop stack later with .\stop-local.ps1 if needed." -ForegroundColor Yellow
            exit 0
        }
    }

    if ($b.N -lt $beats.Count) {
        Clear-Host
        Write-Host ""
        Write-Host ("  BEAT {0} DONE" -f $b.N) -ForegroundColor Green
        Write-Host "  LEFT=product     RIGHT=you" -ForegroundColor DarkCyan
        Write-Hr
        Write-Host ("  Next: Beat {0} -- {1}" -f ($b.N + 1), $beats[$b.N].Title) -ForegroundColor Cyan
        Write-Host "  Switch LEFT to Concierge when the next card says so." -ForegroundColor DarkGray
        $r = Wait-Enter ("[ENTER] start Beat {0}" -f ($b.N + 1))
        if ($r -eq "quit") { exit 0 }
    }
}

Clear-Host
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "       DEMO COMPLETE -- bow / stop recording" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Covered: Chrono-Host | Confirm | Telegram voice Night Out | Calendar/Maps/Split" -ForegroundColor Green
Write-Host "  Full script: docs\demo-script.md" -ForegroundColor DarkGray
Write-Host "  Stop stack:  .\stop-local.ps1" -ForegroundColor DarkGray
Write-Host ""
