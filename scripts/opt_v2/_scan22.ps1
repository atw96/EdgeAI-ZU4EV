$found = [System.Collections.Concurrent.ConcurrentBag[string]]::new()
if (-not $env:BOARD_SUBNET) { throw "set BOARD_SUBNET" }
$ips = 1..254 | ForEach-Object { "$($env:BOARD_SUBNET).$_" }
$ips | ForEach-Object -Parallel {
  $tcp = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $tcp.BeginConnect($_, 22, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(250) -and $tcp.Connected) {
      "$($_)"
    }
  } catch {}
  finally { $tcp.Close() }
} -ThrottleLimit 80
