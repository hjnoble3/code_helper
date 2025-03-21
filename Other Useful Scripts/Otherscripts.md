## Find Last Commit Where a File Was Modified

```sh
git log -1 --pretty=format:"%H - %an, %ar : %s" -- ric\backend\apps\images\main.py
```

## Remove Empty Folders in PowerShell

```powershell
Get-ChildItem -Directory -Recurse | Where-Object { -not $_.GetFiles("*", "AllDirectories") } | Remove-Item -Force -Recurse
```

```cmd
powershell -Command "Get-ChildItem -Directory -Recurse | Where-Object { (Get-ChildItem $_.FullName -Recurse -Force | Where-Object { $_.PSIsContainer -eq $false }) -eq $null } | Remove-Item -Recurse"
```
```cmd
do {
    $emptyFolders = Get-ChildItem -Directory -Recurse | Where-Object {
        -not ($_ | Get-ChildItem -Recurse -Force)
    }
    $emptyFolders | Remove-Item -Recurse -Force
} while ($emptyFolders.Count -gt 0)
```
