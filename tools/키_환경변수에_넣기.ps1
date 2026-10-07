# 옛 .env 에서 API 키를 읽어 Windows 사용자 환경변수에 넣는다 (sky 가 직접 돌린다 · 섹션 7 ②)
#
# ★ 왜 이 스크립트인가 — 키 값은 Claude 가 읽거나 옮기지 않는다 (sky 규칙). 이 스크립트는 값을
#   화면에 찍지 않고, 키 이름과 「넣었다 / 이미 있다」 만 말한다.
# ★ 왜 .env 가 아니라 환경변수인가 — 엔진은 load_dotenv() 로 **지금 폴더의 .env** 만 읽는다
#   (plugin/engine/src/voc_rebuild/engine.py:991 · 1851). 1차는 판마다 작업 폴더가 바뀌어
#   .env 는 판마다 복사해야 한다. 사용자 환경변수는 한 번 넣으면 어느 폴더에서도 잡힌다.
# ★ 옛 저장소는 읽기만 한다 — 고치지도, 지우지도, 옛 코드를 돌리지도 않는다.
# ★ 변수 이름은 영문으로만 쓴다 — Windows PowerShell 5.1 은 BOM 없는 파일을 ANSI 로 읽어
#   한글 변수명이 깨진다. 이 파일은 UTF-8 BOM 으로 저장한다.
#
# 쓰기
#     powershell -ExecutionPolicy Bypass -File "<저장소 자리>\tools\키_환경변수에_넣기.ps1"
#     (옛 .env 가 다른 자리면 -EnvFile "<그 자리>\.env")
#
# 넣은 뒤 — **새 터미널**(또는 Claude Code 를 다시 시작)에서야 보인다. 지금 창에는 안 보인다.

param(
    [string]$EnvFile = "C:\codex\.env",
    [string[]]$Names = @("YOUTUBE_API_KEY", "OPENAI_API_KEY")
)

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Output "못 찾음: $EnvFile"          # 「못 찾음」 은 「없음」 이 아니다 — 여기서 멈춘다
    exit 2
}

$Found = @{}
foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
    $t = $line.Trim()
    if ($t -eq "" -or $t.StartsWith("#") -or -not $t.Contains("=")) { continue }
    $i = $t.IndexOf("=")
    $k = $t.Substring(0, $i).Trim()
    $v = $t.Substring($i + 1).Trim().Trim('"').Trim("'")
    if ($k -ne "" -and $v -ne "") { $Found[$k] = $v }
}

$Added = 0
$Missing = @()
foreach ($k in $Names) {
    $already = [Environment]::GetEnvironmentVariable($k, "User")
    if ($already) {
        Write-Output ("{0,-16} 이미 있다 (그대로 둔다)" -f $k)
        continue
    }
    if (-not $Found.ContainsKey($k)) {
        $Missing += $k
        Write-Output ("{0,-16} .env 에 없다" -f $k)
        continue
    }
    [Environment]::SetEnvironmentVariable($k, $Found[$k], "User")
    $Added = $Added + 1
    Write-Output ("{0,-16} 넣었다 (길이 {1}자 · 값은 찍지 않는다)" -f $k, $Found[$k].Length)
}

Write-Output ""
Write-Output "넣은 것 $Added 개 · .env 에 없던 것 $($Missing.Count) 개"
if ($Added -gt 0) {
    Write-Output "★ 새 터미널(또는 Claude Code 를 다시 시작)에서야 보인다."
}
if ($Missing.Count -gt 0) {
    Write-Output "★ 없던 키는 직접 넣는다 — Windows 설정 > 시스템 > 정보 > 고급 시스템 설정 > 환경 변수 > 사용자 변수"
    exit 1
}
exit 0
