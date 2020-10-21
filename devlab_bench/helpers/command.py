"""
Miscellaneous helpers in the form of classes and/or functions for getting stuff done
"""
import fcntl
import logging
import os
import re
import signal
import subprocess
import time
from devlab_bench.exceptions import DevlabCommandError
from devlab_bench.helpers.common import ISATTY

class Command(object):
    """
    Run a command, and return either stdout as a string or an array of strings
    split by line

    Args:
        path: str, or list for the location of the process to run
        args: list
        ignore_nonzero_rc: bool, whether errors should create logs
        interactive: bool, whether the process should be "interactive"
        split: bool
        suppress_error_out: bool
        stdin: FileHandle, of stdin to send to the process
        timeout: integer, in minutes before the process is aborted <=0 mean no
            timeout. Default=0
        log_output: bool, whether to send the output of the command to the logger
        logger: Logger object to use for messages
    """
    def __init__(self, path, args=None, ignore_nonzero_rc=False, interactive=False, split=True, suppress_error_out=False, stdin=None, timeout=0, log_output=False, logger=None, **kwargs):
        """
        Initialize the command object
        """
        ignored_opts = kwargs
        if not args:
            self.args = []
        else:
            self.args = list(filter(lambda x: x != None, args))
        self.ignore_nonzero_rc = ignore_nonzero_rc
        self.interactive = interactive
        self.path = path
        self.real_path = None
        if logger:
            self.log = logger
        else:
            self.log = logging.getLogger('Command')
        self.log_output = log_output
        self.split = split
        self.suppress_error_out = suppress_error_out
        self.stdin = stdin
        self.timeout = timeout
        self.stdout = []
        self.stderr = []
        self.ctime = time.time()
        self.proc = None
        if log_output and interactive:
            raise DevlabCommandError("ERROR: Setting both 'interactive' and 'log_output' to True won't work")
    def _precheck(self):
        """
        Does some preliminary checks to ensure that executing the script will
        be good, before trying

        Return:
            tuple where:
                First element is an integer... -1 mean failed. 0 means success
                Second element is a message, or the path that was found
        """
        found_path = self.path
        if isinstance(self.path, (list, tuple, set)):
            in_path = False
            for found_path in self.path:
                if os.access(found_path, os.X_OK):
                    in_path = True
                    break
            if not in_path:
                if not self.suppress_error_out:
                    self.log.error("Can't find executable here: %s", self.path)
                    return (-1, "Error! Can't find executable here: {}".format(self.path))
        else:
            if not os.access(self.path, os.X_OK):
                if not self.suppress_error_out:
                    self.log.error("Can't find executable here: %s", self.path)
                return (-1, "Error! Can't find executable here: {}".format(self.path))
        return (0, found_path)
    def _sanitize_string(self, string_to_sanitize): #pylint: disable=no-self-use
        """
        Take a string that needs to be sanitized, and do the following things to it:
            1) Decode it to ascii, ignoring anything that isn't ascii
            2) If there are escape sequences, add an ending escape sequence to the
            3) If there is no terminal, then strip out any escape sequences
        Args:
            string_to_sanitize: The string to sanitize
        Returns
            str
        """
        #self.log.debug("Got original string: '{}'".format("%r" % string_to_sanitize))
        if not string_to_sanitize:
            return string_to_sanitize
        sanitized = string_to_sanitize.decode('ascii', 'ignore')
        sanitized = sanitized.strip()
        if ISATTY:
            if '\033[' in sanitized:
                #Append ending escape sequence to the string
                sanitized += '\033[0m'
        else:
            #Remove ending escape from string
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            sanitized = ansi_escape.sub('', sanitized)
        #self.log.debug("Converted to: '{}'".format("%r" % sanitized))
        return sanitized
    def _process_output(self, max_lines=100, flush=False):
        line_count = 0
        cur_check = 0
        max_checks = 100
        if flush:
            for pipe in (self.proc.stdout, self.proc.stderr):
                try:
                    pipe.flush()
                except AttributeError:
                    pass
        while cur_check <= max_checks or flush:
            stdout_empty = False
            stderr_empty = False
            try:
                stdout_line = None
                stderr_line = None
                if self.proc.stdout is not None:
                    try:
                        stdout_line = self._sanitize_string(self.proc.stdout.readline())
                    except IOError:
                        stdout_line = None
                if self.proc.stderr is not None:
                    try:
                        stderr_line = self._sanitize_string(self.proc.stderr.readline())
                    except IOError:
                        stderr_line = None
                if stdout_line:
                    if self.log_output:
                        self.log.info(stdout_line)
                    self.stdout.append(stdout_line)
                    line_count += 1
                else:
                    stdout_empty = True
                if stderr_line:
                    if self.log_output:
                        self.log.warning(stderr_line)
                    self.stderr.append(stderr_line)
                    line_count += 1
                else:
                    stderr_empty = True
                if not flush:
                    #If both pipes are empty, then return/break out.
                    if stdout_empty and stderr_empty:
                        break
                    #Even if there is still data in the pipes, return back control if max_lines is reached
                    if line_count >= max_lines:
                        break
                else:
                    #No new lines from either pipe, and process has ended. Flush complete
                    if (stdout_empty and stderr_empty) and self.proc.poll() is not None:
                        #Get any non-newline separate content that is left
                        if self.proc.stdout:
                            stdout_dangle = self._sanitize_string(self.proc.stdout.read())
                            if stdout_dangle:
                                if self.log_output:
                                    self.log.info(stdout_dangle)
                                self.stdout.append(stdout_dangle)
                        if self.proc.stderr:
                            stderr_dangle = self._sanitize_string(self.proc.stderr.read())
                            if stderr_dangle:
                                if self.log_output:
                                    self.log.error(stderr_dangle)
                                self.stderr.append(stderr_dangle)
                        break
            except OSError:
                pass
            cur_check += 1
    def _wait_for_proc(self):
        """
        Wait for the running process to finish running and process any output
        that the process has generated while waiting. This is also responsible
        for watching the process for any timeouts
        """
        #Check every .1 seconds if the process is hung or not.
        #hung means it waited longer than self.timeout
        self.log.debug("Watching process (pid=%s) for completion or if hung", self.proc.pid)
        while self.proc.poll() is None:
            cur_time = time.time()
            #Write any error messages from the process using our logger
            self._process_output()
            #If our process has been running longer than self.timeout
            #then we should see if it is hung or something
            if self.timeout > 0:
                if cur_time - self.ctime > self.timeout * 60:
                    self.log.warning("Command: '%s'(pid=%s): appears to be hung, attempting to stop and/or kill it", ' '.join([self.real_path] + self.args), self.proc.pid)
                    self.proc.terminate()
                    wait_count = 0
                    while self.proc.poll() is None:
                        if wait_count >= 20:
                            self.log.warning("Command: '%s'(pid=%s): Didn't die, forcefully killing it", ' '.join([self.real_path] + self.args), self.proc.pid)
                            self.proc.kill()
                            self.proc.wait()
                            self._process_output(flush=True)
                            self.proc.communicate()
                            break
                        time.sleep(1)
                        wait_count += 1
            time.sleep(0.01)
        #Write any remaining log messages in the pipe
        self._process_output(flush=True)
        #This is needed so that the process can clean up its stdout/err pipes
        self.proc.communicate()
    def die(self, graceful=True):
        """
        Make any running process go away

        Args:
            graceful: bool, whether to try and gracefully kill process (INT),
                to send a SIGKILL signal
        """
        if self.proc:
            if graceful:
                self.proc.send_signal(signal.SIGINT)
                wait_count = 0
                while self.proc.poll() is None:
                    if wait_count >= 20:
                        self.proc.kill()
                        self.proc.wait()
                        break
                    time.sleep(1)
                    wait_count += 1
            else:
                self.proc.kill()
                self.proc.wait()
    def run(self):
        """
        Execute the command

        Returns:
            tuple where:
                First Element is the return code of the command
                Second Element is either a list of strings OR a str (if split==false)
        """
        precheck_res = self._precheck()
        if precheck_res[0] < 0:
            return precheck_res
        self.real_path = precheck_res[1]
        subprocess_args = {
            'shell': False
        }
        if not self.interactive:
            subprocess_args['stdout'] = subprocess.PIPE
            subprocess_args['stderr'] = subprocess.PIPE
        if self.stdin:
            subprocess_args['stdin'] = self.stdin
        self.log.debug("Running command: '%s'", ' '.join([self.real_path] + self.args))
        self.ctime = time.time()
        self.proc = subprocess.Popen([self.real_path] + self.args, **subprocess_args)
        for strm in (self.proc.stdout, self.proc.stderr):
            if strm is not None:
                fno = strm.fileno()
                fl_nb = fcntl.fcntl(fno, fcntl.F_GETFL)
                fcntl.fcntl(fno, fcntl.F_SETFL, fl_nb | os.O_NONBLOCK)
        self._wait_for_proc()
        if self.proc.returncode > 0:
            if not self.suppress_error_out:
                if not self.ignore_nonzero_rc:
                    self.log.error("Command did not exit with successful status code (%s): '%s %s'", self.proc.returncode, self.real_path, ' '.join(self.args))
                if self.stdout and not self.log_output:
                    for line in self.stdout:
                        self.log.error(line)
                if self.stderr and not self.log_output:
                    for line in self.stderr:
                        self.log.error(line)
            out = self.stderr
            if not self.stderr:
                if self.stdout:
                    out = self.stdout
                else:
                    out = ''
        else:
            if self.stdout:
                out = self.stdout
            else:
                out = ''
        if not self.split:
            out = '\n'.join(out)
        return (self.proc.returncode, out)
