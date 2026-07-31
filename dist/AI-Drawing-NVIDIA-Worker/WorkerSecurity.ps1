$script:SystemSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-18")
$script:AdministratorsSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-32-544")
$script:AllowedUpdaterSids = @(
    $script:SystemSid.Value
    $script:AdministratorsSid.Value
)

function Assert-NotReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Task 7 migration is required: an updater-owned path is a reparse point."
    }
}

function Set-SecureUpdaterRootAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-NotReparsePoint -Path $Path
    $Acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $Acl.SetOwner($script:SystemSid)
    $Acl.SetAccessRuleProtection($true, $false)
    foreach ($Rule in @($Acl.Access)) {
        [void]$Acl.RemoveAccessRuleSpecific($Rule)
    }
    $Inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($Sid in @($script:SystemSid, $script:AdministratorsSid)) {
        $Rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $Sid,
            [Security.AccessControl.FileSystemRights]::FullControl,
            $Inheritance,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        )
        [void]$Acl.AddAccessRule($Rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $Acl -ErrorAction Stop
}

function Reset-SecureUpdaterChildAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-NotReparsePoint -Path $Path
    $Acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $Acl.SetOwner($script:SystemSid)
    $Acl.SetAccessRuleProtection($false, $false)
    foreach ($Rule in @($Acl.Access | Where-Object { -not $_.IsInherited })) {
        [void]$Acl.RemoveAccessRuleSpecific($Rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $Acl -ErrorAction Stop
}

function Assert-SecureUpdaterPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$RequireProtected
    )

    Assert-NotReparsePoint -Path $Path
    $Acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $Owner = $Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($Owner -ne $script:SystemSid.Value) {
        throw "Task 7 migration is required: updater path owner is not SYSTEM."
    }
    if ($RequireProtected -and -not $Acl.AreAccessRulesProtected) {
        throw "Task 7 migration is required: updater root ACL inherits untrusted rules."
    }
    $Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($Rules.Count -ne 2) {
        throw "Task 7 migration is required: updater ACL has unexpected entries."
    }
    $Seen = @{}
    foreach ($Rule in $Rules) {
        $Principal = $Rule.IdentityReference.Value
        if (
            $script:AllowedUpdaterSids -notcontains $Principal -or
            $Rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $Rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            $Seen.ContainsKey($Principal)
        ) {
            throw "Task 7 migration is required: updater ACL grants an unexpected principal or right."
        }
        $Seen[$Principal] = $true
    }
    foreach ($RequiredSid in $script:AllowedUpdaterSids) {
        if (-not $Seen.ContainsKey($RequiredSid)) {
            throw "Task 7 migration is required: updater ACL is missing a required principal."
        }
    }
}

function Get-UpdaterTreeNoFollow {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Root = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    $Pending = New-Object "System.Collections.Generic.Stack[System.IO.FileSystemInfo]"
    $Items = New-Object "System.Collections.Generic.List[System.IO.FileSystemInfo]"
    $Pending.Push($Root)
    while ($Pending.Count -gt 0) {
        $Item = $Pending.Pop()
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Task 7 migration is required: an updater-owned path is a reparse point."
        }
        $Items.Add($Item)
        if ($Item.PSIsContainer) {
            foreach ($Child in @(Get-ChildItem -LiteralPath $Item.FullName -Force -ErrorAction Stop)) {
                if (($Child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw "Task 7 migration is required: an updater-owned path is a reparse point."
                }
                $Pending.Push($Child)
            }
        }
    }
    return $Items.ToArray()
}

function Protect-UpdaterTree {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Tree = @(Get-UpdaterTreeNoFollow -Path $Path)
    Set-SecureUpdaterRootAcl -Path $Tree[0].FullName
    foreach ($Child in @($Tree | Select-Object -Skip 1)) {
        Reset-SecureUpdaterChildAcl -Path $Child.FullName
    }
    Assert-SecureUpdaterTree -Path $Path
}

function Assert-SecureUpdaterTree {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Tree = @(Get-UpdaterTreeNoFollow -Path $Path)
    Assert-SecureUpdaterPath -Path $Tree[0].FullName -RequireProtected
    foreach ($Child in @($Tree | Select-Object -Skip 1)) {
        Assert-SecureUpdaterPath -Path $Child.FullName
    }
}

function Assert-ExistingWorkerRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-NotReparsePoint -Path $Path
    $Marker = Join-Path $Path ".ai-drawing-worker-owned"
    try {
        $MarkerContents = (Get-Content -LiteralPath $Marker -Raw -Encoding UTF8 -ErrorAction Stop).Trim()
    } catch {
        throw "Task 7 migration is required: the Worker ownership marker is missing."
    }
    if ($MarkerContents -ne "AI-Drawing NVIDIA Worker") {
        throw "Task 7 migration is required: the Worker ownership marker is invalid."
    }
    Assert-SecureUpdaterPath -Path $Path -RequireProtected
    Assert-SecureUpdaterPath -Path $Marker
    foreach ($Relative in @("updater-runtime", "updater")) {
        $Candidate = Join-Path $Path $Relative
        if (Test-Path -LiteralPath $Candidate) {
            Assert-SecureUpdaterTree -Path $Candidate
        }
    }
}
