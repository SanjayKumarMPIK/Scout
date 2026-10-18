param(
    [Parameter(Mandatory=$true)]
    [string]$ImagePath
)

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    Add-Type -AssemblyName System.IO

    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

    Function Await($WinRtTask, $ResultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(-1) | Out-Null
        $netTask.Result
    }

    [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

    if (-not (Test-Path $ImagePath)) {
        $errObj = @{ success = $false; error = "Image path does not exist: $ImagePath" }
        $jsonStr = ConvertTo-Json $errObj
        $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonStr))
        Write-Output "OCR_BASE64:$b64"
        exit 0
    }

    $bytes = [System.IO.File]::ReadAllBytes($ImagePath)
    $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
    $writer = [Windows.Storage.Streams.DataWriter]::new($stream)
    $writer.WriteBytes($bytes)
    $null = Await ($writer.StoreAsync()) ([System.UInt32])
    $writer.DetachStream() | Out-Null
    $stream.Seek(0)

    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $softwareBitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) {
        $errObj = @{ success = $false; error = "Windows OCR engine could not be initialized." }
        $jsonStr = ConvertTo-Json $errObj
        $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonStr))
        Write-Output "OCR_BASE64:$b64"
        exit 0
    }

    $ocrResult = Await ($engine.RecognizeAsync($softwareBitmap)) ([Windows.Media.Ocr.OcrResult])

    # Sanitize control characters that can corrupt JSON
    $cleanFullText = [regex]::Replace($ocrResult.Text, "[\x00-\x08\x0B\x0C\x0E-\x1F]", " ")

    $linesData = @()
    foreach ($line in $ocrResult.Lines) {
        $cleanLineText = [regex]::Replace($line.Text, "[\x00-\x08\x0B\x0C\x0E-\x1F]", " ")
        $wordsData = @()
        foreach ($word in $line.Words) {
            $cleanWordText = [regex]::Replace($word.Text, "[\x00-\x08\x0B\x0C\x0E-\x1F]", " ")
            $rect = $word.BoundingRect
            $wordsData += @{
                text = $cleanWordText
                x = [math]::Round($rect.X)
                y = [math]::Round($rect.Y)
                width = [math]::Round($rect.Width)
                height = [math]::Round($rect.Height)
                center_x = [math]::Round($rect.X + ($rect.Width / 2))
                center_y = [math]::Round($rect.Y + ($rect.Height / 2))
            }
        }
        
        if ($wordsData.Count -gt 0) {
            $minX = [math]::Round(($wordsData | Measure-Object -Property x -Minimum).Minimum)
            $minY = [math]::Round(($wordsData | Measure-Object -Property y -Minimum).Minimum)
            $maxX = [math]::Round(($wordsData | ForEach-Object { $_.x + $_.width } | Measure-Object -Maximum).Maximum)
            $maxY = [math]::Round(($wordsData | ForEach-Object { $_.y + $_.height } | Measure-Object -Maximum).Maximum)
        } else {
            $minX = 0; $minY = 0; $maxX = 0; $maxY = 0
        }

        $lineW = [math]::Max(0, ($maxX - $minX))
        $lineH = [math]::Max(0, ($maxY - $minY))

        $linesData += @{
            text = $cleanLineText
            x = $minX
            y = $minY
            width = $lineW
            height = $lineH
            center_x = [math]::Round($minX + ($lineW / 2))
            center_y = [math]::Round($minY + ($lineH / 2))
            words = $wordsData
        }
    }

    $output = @{
        success = $true
        text = $cleanFullText
        line_count = $linesData.Count
        lines = $linesData
    }

    $jsonStr = ConvertTo-Json $output -Depth 4
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonStr))
    Write-Output "OCR_BASE64:$b64"
}
catch {
    $errObj = @{
        success = $false
        error = $_.Exception.Message
    }
    $jsonStr = ConvertTo-Json $errObj
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonStr))
    Write-Output "OCR_BASE64:$b64"
}
