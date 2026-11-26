# Lance une commande sur la base Postgres et le Vault locaux (compose.dev.yaml) au lieu de Supabase et du vrai Vault.
#   .\local.ps1 migrate          .\local.ps1 seed_db          .\local.ps1 runserver
#   .\local.ps1 create_staff_user admin admin@example.com      .\local.ps1 pytest
# Ces variables ne valent que le temps de la commande : le reste de ton terminal (et le .env) ne change pas.
$local = @{
    DB_HOST = '127.0.0.1'; DB_PORT = '5433'; DB_NAME = 'haeron'; DB_USER = 'haeron'; DB_PASSWORD = 'haeron'
    VAULT_ADDR = 'http://127.0.0.1:8201'; VAULT_TOKEN = 'haeron-dev'
}
$previous = @{}
foreach ($name in $local.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $local[$name], 'Process')
}
Push-Location $PSScriptRoot
try {
    if ($args.Count -gt 0 -and $args[0] -eq 'pytest') {
        uv run pytest @($args | Select-Object -Skip 1)
    }
    else {
        uv run python src/manage.py @args
    }
}
finally {
    Pop-Location
    foreach ($name in $previous.Keys) {
        # une variable absente avant doit etre supprimee : PowerShell 7.5 garderait une valeur vide,
        # qui masquerait ensuite le .env (base sans nom, Vault sans adresse)
        if ($null -eq $previous[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    }
}
