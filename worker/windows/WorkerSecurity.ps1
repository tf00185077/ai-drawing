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

function New-UpdaterDirectorySecurity {
    param(
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier]$OwnerSid,
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier[]]$AllowedSids
    )

    if ($AllowedSids.Count -lt 1) {
        throw "Updater directory ACL requires at least one principal."
    }
    $Security = New-Object Security.AccessControl.DirectorySecurity
    $Security.SetOwner($OwnerSid)
    $Security.SetAccessRuleProtection($true, $false)
    $Inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($Sid in $AllowedSids) {
        $Rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $Sid,
            [Security.AccessControl.FileSystemRights]::FullControl,
            $Inheritance,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        )
        [void]$Security.AddAccessRule($Rule)
    }
    return $Security
}

function Assert-ExpectedUpdaterAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier]$OwnerSid,
        [Parameter(Mandatory = $true)][Security.Principal.SecurityIdentifier[]]$AllowedSids,
        [switch]$RequireProtected,
        [switch]$RequireInheritable
    )

    Assert-NotReparsePoint -Path $Path
    $Acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $Owner = $Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($Owner -ne $OwnerSid.Value) {
        throw "Task 7 migration is required: updater path owner is unexpected."
    }
    if ($RequireProtected -and -not $Acl.AreAccessRulesProtected) {
        throw "Task 7 migration is required: updater root ACL inherits untrusted rules."
    }
    $AllowedValues = @($AllowedSids | ForEach-Object { $_.Value })
    $Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($Rules.Count -ne $AllowedValues.Count) {
        throw "Task 7 migration is required: updater ACL has unexpected entries."
    }
    $ExpectedInheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $Seen = @{}
    foreach ($Rule in $Rules) {
        $Principal = $Rule.IdentityReference.Value
        if (
            $AllowedValues -notcontains $Principal -or
            $Rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $Rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            ($RequireInheritable -and $Rule.InheritanceFlags -ne $ExpectedInheritance) -or
            ($RequireInheritable -and $Rule.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None) -or
            $Seen.ContainsKey($Principal)
        ) {
            throw "Task 7 migration is required: updater ACL grants an unexpected principal or right."
        }
        $Seen[$Principal] = $true
    }
    foreach ($RequiredSid in $AllowedValues) {
        if (-not $Seen.ContainsKey($RequiredSid)) {
            throw "Task 7 migration is required: updater ACL is missing a required principal."
        }
    }
}

function New-SecureUpdaterDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Security.Principal.SecurityIdentifier]$OwnerSid = $script:SystemSid,
        [Security.Principal.SecurityIdentifier[]]$AllowedSids = @(
            $script:SystemSid,
            $script:AdministratorsSid
        )
    )

    $TargetPath = [IO.Path]::GetFullPath($Path)
    $ParentPath = [IO.Path]::GetDirectoryName($TargetPath)
    $Parent = Get-Item -LiteralPath $ParentPath -Force -ErrorAction Stop
    if (-not $Parent.PSIsContainer) {
        throw "Secure updater directory parent is invalid."
    }
    Assert-NotReparsePoint -Path $Parent.FullName
    if ([IO.Directory]::Exists($TargetPath) -or [IO.File]::Exists($TargetPath)) {
        throw "Task 7 migration is required: secure updater directory already exists."
    }

    $Leaf = [IO.Path]::GetFileName($TargetPath.TrimEnd([IO.Path]::DirectorySeparatorChar))
    $Nonce = [Guid]::NewGuid().ToString("N")
    $StagingPath = Join-Path $Parent.FullName ".$Leaf.secure-$Nonce"
    $IdentityName = ".secure-directory-$Nonce"
    $IdentityPath = Join-Path $StagingPath $IdentityName
    $Moved = $false
    try {
        $Security = New-UpdaterDirectorySecurity -OwnerSid $OwnerSid -AllowedSids $AllowedSids
        [void][IO.Directory]::CreateDirectory($StagingPath, $Security)
        Assert-ExpectedUpdaterAcl -Path $StagingPath -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids -RequireProtected -RequireInheritable
        [IO.File]::WriteAllText($IdentityPath, $Nonce, (New-Object Text.UTF8Encoding -ArgumentList $false))
        Assert-ExpectedUpdaterAcl -Path $IdentityPath -OwnerSid $OwnerSid -AllowedSids $AllowedSids
        [IO.Directory]::Move($StagingPath, $TargetPath)
        $Moved = $true
        $MovedIdentity = Join-Path $TargetPath $IdentityName
        if ([IO.File]::ReadAllText($MovedIdentity) -ne $Nonce) {
            throw "Secure updater directory identity verification failed."
        }
        Assert-ExpectedUpdaterAcl -Path $TargetPath -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids -RequireProtected -RequireInheritable
        Assert-ExpectedUpdaterAcl -Path $MovedIdentity -OwnerSid $OwnerSid -AllowedSids $AllowedSids
        [IO.File]::Delete($MovedIdentity)
        Assert-ExpectedUpdaterAcl -Path $TargetPath -OwnerSid $OwnerSid `
            -AllowedSids $AllowedSids -RequireProtected -RequireInheritable
    } finally {
        if (-not $Moved -and [IO.Directory]::Exists($StagingPath)) {
            Assert-ExpectedUpdaterAcl -Path $StagingPath -OwnerSid $OwnerSid `
                -AllowedSids $AllowedSids -RequireProtected -RequireInheritable
            [IO.Directory]::Delete($StagingPath, $true)
        }
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

    Assert-ExpectedUpdaterAcl -Path $Path -OwnerSid $script:SystemSid `
        -AllowedSids @($script:SystemSid, $script:AdministratorsSid) `
        -RequireProtected:$RequireProtected -RequireInheritable:$RequireProtected
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
