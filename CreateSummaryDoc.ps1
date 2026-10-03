$summary = Get-Content -Path "README.txt" -Raw
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Add()
$selection = $word.Selection
$selection.TypeText($summary)
$doc.SaveAs([ref]"ProjectSummary.docx")
$word.Quit()