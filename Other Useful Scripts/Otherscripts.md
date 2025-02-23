## Find Last Commit Where a File Was Modified

```sh
git log -1 --pretty=format:"%H - %an, %ar : %s" -- ric\backend\apps\images\main.py
```

## Remove Empty Folders in PowerShell

```powershell
Get-ChildItem -Directory -Recurse | Where-Object { -not $_.GetFiles("*", "AllDirectories") } | Remove-Item -Force -Recurse
```
