# GitHub-Repo anlegen und pushen

## Repo-Name

- Owner: `kolossboss`
- Repository: `homequests-backend-ha`

## Beispielbefehle

```bash
cd /Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration
git init
git checkout -b codex/homequests-backend-ha
git add .
git commit -m "Add HomeQuests Home Assistant custom integration"
gh repo create kolossboss/homequests-backend-ha --public --source=. --remote=origin --push
```

## Falls das Repo bereits existiert

```bash
cd /Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration
git init
git checkout -b codex/homequests-backend-ha
git remote add origin git@github.com:kolossboss/homequests-backend-ha.git
git add .
git commit -m "Add HomeQuests Home Assistant custom integration"
git push -u origin codex/homequests-backend-ha
```
