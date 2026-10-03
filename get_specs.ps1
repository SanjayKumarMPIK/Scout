$cpu = (Get-CimInstance Win32_Processor).Name
$gpu = (Get-CimInstance Win32_VideoController | Select-Object -First 1).Name
$ram = ((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum) / 1GB
$disk = ((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").Size) / 1GB
$text = "CPU: $cpu`nGPU: $gpu`nRAM: {0:N2} GB`nStorage (C:): {1:N2} GB" -f $ram, $disk
Set-Content -Path specs.txt -Value $text -Encoding UTF8
