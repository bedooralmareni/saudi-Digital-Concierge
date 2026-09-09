<#
=====================================================================
 Create-InvoiceTrackingList.ps1
 Builds the "Invoice Tracking" SharePoint Online list to spec:
 columns, types, choice values, date-only formatting, indexes,
 unique Invoice Number, a curated default view, and versioning.
 Run once against your site.

 REQUIREMENTS
   - PnP.PowerShell module:  Install-Module PnP.PowerShell -Scope CurrentUser
   - Permission to create lists on the target site
   - PowerShell 7+ recommended
   - An Entra ID app registration for interactive login (see AUTH below)

 AUTH (PnP.PowerShell 2.x, Sept 2024+)
   The old built-in multi-tenant app was removed, so -Interactive now
   REQUIRES your own ClientId. One-time setup per tenant:

     Register-PnPEntraIDAppForInteractiveLogin `
         -ApplicationName "PnP Interactive" `
         -Tenant yourtenant.onmicrosoft.com

   Copy the resulting Application (client) ID into $ClientId below.

 USAGE
   1. Edit $SiteUrl, $ListName, and $ClientId below.
   2. Run:  ./Create-InvoiceTrackingList.ps1
   3. Sign in when the browser opens.

 NOTE: this creates an EMPTY list with the correct schema. Loading
 your 900 existing rows is a separate step (see bottom of file).

 IF IT FAILS PART-WAY: the guard below stops on an existing list to
 avoid clobbering it. If a run died mid-build, delete the half-made
 list first  ->  Remove-PnPList -Identity $ListName -Force  <-  then re-run.
=====================================================================
#>

# ---------------------------------------------------------------
# CONFIG  ->  EDIT THESE THREE LINES
# ---------------------------------------------------------------
$SiteUrl  = "https://algihaz-my.sharepoint.com/personal/bedoor_alsulami_algihaz_com"
$ListName = "Invoice Tracking"
$ClientId = "00000000-0000-0000-0000-000000000000"   # from Register-PnPEntraIDAppForInteractiveLogin

# --------------clear-------------------------------------------------
# CONNECT
# ---------------------------------------------------------------
Write-Host "Connecting to $SiteUrl ..." -ForegroundColor Cyan
Connect-PnPOnline -Url $SiteUrl -Interactive -ClientId $ClientId

# ---------------------------------------------------------------
# CREATE LIST + ENABLE VERSIONING (audit trail for RPA writes)
# ---------------------------------------------------------------
if (Get-PnPList -Identity $ListName -ErrorAction SilentlyContinue) {
    Write-Warning "List '$ListName' already exists. Stopping to avoid changes."
    return
}
New-PnPList -Title $ListName -Template GenericList -OnQuickLaunch | Out-Null
Set-PnPList -Identity $ListName -EnableVersioning $true -MajorVersions 200
Write-Host "List created + versioning on." -ForegroundColor Green

# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------
function Add-DateField($internal, $display, $desc="") {
    # No -AddToDefaultView: the default view is curated explicitly at the end.
    Add-PnPField -List $ListName -DisplayName $display -InternalName $internal `
                 -Type DateTime | Out-Null
    # DisplayFormat 0 = Date only (no time)
    Set-PnPField -List $ListName -Identity $internal -Values @{ DisplayFormat = 0 } | Out-Null
    if ($desc) { Set-PnPField -List $ListName -Identity $internal -Values @{ Description = $desc } | Out-Null }
}
function Set-Indexed($internal) {
    Set-PnPField -List $ListName -Identity $internal -Values @{ Indexed = $true } | Out-Null
}

# ---------------------------------------------------------------
# TITLE COLUMN  ->  repurpose as Invoice Number (required, indexed, UNIQUE)
# ---------------------------------------------------------------
Set-PnPField -List $ListName -Identity "Title" -Values @{ Title = "Invoice Number"; Required = $true } | Out-Null
Set-Indexed "Title"
# Enforce uniqueness so the RPA/flow can never create a duplicate invoice.
# NOTE: during the 900-row load, any duplicate Invoice Number will be REJECTED. Clean the source first.
Set-PnPField -List $ListName -Identity "Title" -Values @{ EnforceUniqueValues = $true } | Out-Null

# ---------------------------------------------------------------
# CHOICE COLUMNS
# ---------------------------------------------------------------
Add-PnPField -List $ListName -DisplayName "Invoice Type" -InternalName "InvoiceType" -Type Choice `
    -Choices "Advance Invoice","Change Order","FAC","TCC","Progress Invoice" | Out-Null

Add-PnPField -List $ListName -DisplayName "Approval Status" -InternalName "ApprovalStatus" -Type Choice `
    -Choices "For Submission","Pre-Confirmation","Under SAP Portal Approval","Under ETIMAD Portal Approval",`
             "Under ETIMAD Finance","Under ETIMAD Treasury","Under Client PMT Approval","Returned with Comments",`
             "Doc Sent to SE Treasury","Forwarded to SE Finance","Partially Paid","Paid / Collected","Cancelled" | Out-Null
Set-Indexed "ApprovalStatus"   # RPA writes here; Power BI groups on it

# Project Name / Short Name kept as TEXT so the script runs without your full project list.
# RECOMMENDED later: convert to Choice, or a lookup to a "Projects" list, for consistent grouping in Power BI.
Add-PnPField -List $ListName -DisplayName "Project Name"       -InternalName "ProjectName"      -Type Text | Out-Null
Add-PnPField -List $ListName -DisplayName "Project Short Name" -InternalName "ProjectShortName" -Type Text | Out-Null

# ---------------------------------------------------------------
# TEXT / REFERENCE COLUMNS
# ---------------------------------------------------------------
Add-PnPField -List $ListName -DisplayName "Contract Number" -InternalName "ContractNumber" -Type Text | Out-Null
Add-PnPField -List $ListName -DisplayName "SEC PO Number"   -InternalName "SECPONumber"    -Type Text | Out-Null

# ---------------------------------------------------------------
# AMOUNT COLUMNS  (Currency = SAR; format can be tuned in list settings)
# ---------------------------------------------------------------
Add-PnPField -List $ListName -DisplayName "Gross Amount (SAR)"          -InternalName "GrossAmount"       -Type Currency | Out-Null
Add-PnPField -List $ListName -DisplayName "Net Amount incl. VAT (SAR)"  -InternalName "NetAmountInclVAT"  -Type Currency | Out-Null
Add-PnPField -List $ListName -DisplayName "Net Amount excl. VAT (SAR)"  -InternalName "NetAmountExclVAT"  -Type Currency | Out-Null

# ---------------------------------------------------------------
# DATE COLUMNS  (all date-only)
# TODO: replace the (code) descriptions once you confirm what DD / PD / NDD mean.
# ---------------------------------------------------------------
Add-DateField "FirstSubmissionDate"   "First Submission Date"
Add-DateField "FinalInvoiceDate"      "Final Invoice Date"       "Code: DD"
Add-DateField "OracleUploadDate"      "Oracle Upload Date"       "Final Submission / Oracle uploading"
Add-DateField "InvoiceApprovalDate"   "Invoice Approval Date"
Add-DateField "PortalSubmissionDate"  "Portal Submission Date"   "Client SAP portal submission (RPA writes this)"
Add-DateField "PortalAcceptanceDate"  "Portal Acceptance Date"   "Client SAP portal acceptance (RPA writes this)"
Add-DateField "DocSentDate"           "Doc Sent Date"            "Code: PD"
Add-DateField "ExpectedPaymentDate"   "Expected Payment Date"    "Code: NDD"
Add-DateField "PaymentCollectionDate" "Payment Collection Date"
Set-Indexed "FirstSubmissionDate"

# ---------------------------------------------------------------
# NEW COLUMNS the project needs (bot targets + measurement)
# ---------------------------------------------------------------
Add-PnPField -List $ListName -DisplayName "Signed Doc Retrieved" -InternalName "SignedDocRetrieved" -Type Boolean | Out-Null
Add-PnPField -List $ListName -DisplayName "Signed Doc Link"      -InternalName "SignedDocLink"      -Type URL     | Out-Null
Add-DateField "StatusLastChanged" "Status Last Changed" "Stamped by RPA each sync; powers aging alerts"
Add-PnPField -List $ListName -DisplayName "Source" -InternalName "Source" -Type Choice `
    -Choices "QS Email","Form","Manual" | Out-Null
Add-PnPField -List $ListName -DisplayName "QS Submitter" -InternalName "QSSubmitter" -Type User | Out-Null
Add-PnPField -List $ListName -DisplayName "Notes" -InternalName "Notes" -Type Note | Out-Null

# ---------------------------------------------------------------
# DEFAULT VIEW  ->  curated, not all ~25 columns (keeps it readable)
# Everything else is still there for custom views / Power Query / Power BI.
# ---------------------------------------------------------------
$defaultViewFields = @(
    "Title",                # Invoice Number
    "InvoiceType",
    "ApprovalStatus",
    "ProjectShortName",
    "NetAmountInclVAT",
    "FirstSubmissionDate",
    "PortalSubmissionDate",
    "ExpectedPaymentDate",
    "PaymentCollectionDate",
    "SignedDocRetrieved",
    "StatusLastChanged"
)
Set-PnPView -List $ListName -Identity "All Items" -Fields $defaultViewFields | Out-Null
Write-Host "Default view curated to $($defaultViewFields.Count) columns." -ForegroundColor Green

# ---------------------------------------------------------------
# DONE
# ---------------------------------------------------------------
Write-Host "`n'$ListName' built successfully." -ForegroundColor Green
Write-Host "Indexed: Invoice Number (unique), Approval Status, First Submission Date." -ForegroundColor Green
Write-Host "Next: load your 900 rows (see notes at bottom of this script)." -ForegroundColor Yellow

<#
=====================================================================
 LOADING YOUR 900 ROWS  (do this after the list exists)
=====================================================================
 Option A (easiest): a Power Automate flow "List rows in an Excel
 table" -> "Create item", mapping each Excel column to the internal
 names above. Good for a one-time load and reusable later.

 Option B (fast, scripted): save the cleaned Excel as CSV, then:

   $rows = Import-Csv "./invoices.csv"
   foreach ($r in $rows) {
     Add-PnPListItem -List "Invoice Tracking" -Values @{
       "Title"               = $r.'Invoice No.'
       "InvoiceType"         = $r.'Invoice type'
       "ProjectName"         = $r.'Project Name'
       "ApprovalStatus"      = $r.'Approval Status'
       "GrossAmount"         = $r.'Gross Invoice Amount'
       "FirstSubmissionDate" = $r.'First Submittion Date'
       # ...map the rest...
     }
   }

 WATCH:
   - dates must parse as dates (dd/mm/yyyy vs mm/dd),
   - choice values in the file must EXACTLY match the choices above,
   - Invoice Number must be UNIQUE (EnforceUniqueValues is on) — any
     duplicate row will fail. Clean the file first.
=====================================================================
#>
