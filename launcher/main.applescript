on run
	set appRoot to POSIX path of (path to me)
	set installerPath to appRoot & "Contents/Resources/workbench/install-persistent.command"
	do shell script "/bin/zsh " & quoted form of installerPath
	open location "http://127.0.0.1:8788/"
end run
