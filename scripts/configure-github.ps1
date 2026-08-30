param(
    [string]$Repository = "naveenhydpk19/ai-gitops-platform",
    [string]$SourceBranch = "master"
)

$ErrorActionPreference = "Stop"

gh auth status | Out-Null
$existing = gh repo view $Repository --json name 2>$null
if (-not $existing) {
    gh repo create $Repository --public --description "AI-governed EKS GitOps delivery platform"
}

$remote = git remote get-url github 2>$null
if (-not $remote) {
    git remote add github "https://github.com/$Repository.git"
}

gh api --method PUT "repos/$Repository/environments/dev" | Out-Null
gh api --method PUT "repos/$Repository/environments/qa" | Out-Null
gh api --method PUT "repos/$Repository/environments/production" | Out-Null

$labels = gh label list --repo $Repository --json name --jq '.[].name'
if ($labels -notcontains "change-approved") {
    gh label create change-approved --repo $Repository --color 1F883D --description "Change request approved for production"
}

Write-Host "GitHub prerequisites are configured for $Repository."
Write-Host "Add required reviewers to the production environment in repository settings before deployment."
Write-Host "Push with: git push github ${SourceBranch}:master"