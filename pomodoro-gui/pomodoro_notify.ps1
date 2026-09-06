$xml = @"<toast duration="short"><visual><binding template="ToastGeneric"><text>Pomodoro Done</text><text>1 minute elapsed.</text></binding></visual></toast>@"
$doc = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastGeneric)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("HermesPomodoro").Show($toast)
