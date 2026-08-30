param(
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"
$terraformDirectory = Join-Path $PSScriptRoot "..\infra\terraform"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $terraformDirectory
try {
    terraform init
    terraform validate
    if ($AutoApprove) {
        terraform apply -auto-approve
    } else {
        terraform apply
    }
    $cluster = terraform output -raw cluster_name
    $repository = terraform output -raw ecr_repository_url
} finally {
    Pop-Location
}

aws eks update-kubeconfig --region us-east-1 --name $cluster

Get-ChildItem (Join-Path $repositoryRoot "gitops\environments") -Filter values.yaml -Recurse | ForEach-Object {
    (Get-Content $_.FullName -Raw).Replace("REPLACE_WITH_ECR_REPOSITORY", $repository) |
        Set-Content $_.FullName
}

kubectl wait --namespace argocd --for=condition=Available deployment/argocd-server --timeout=10m
kubectl apply -f (Join-Path $repositoryRoot "gitops\argocd\applicationset.yaml")

Write-Host "EKS and Argo CD are ready. Commit and push the generated ECR repository values."
Write-Host "Set GitHub repository variable AWS_RELEASE_ROLE_ARN to:"
Push-Location $terraformDirectory
try { terraform output -raw github_release_role_arn } finally { Pop-Location }