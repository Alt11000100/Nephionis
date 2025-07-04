class TimeoutHandler:
    """ 
    A class for implementing a timeout thread that can raise a warning or kill a process
    whenever it exceeds a timeout.

    ...

    Attributes
    ----------
    timeout : int
        Timeout in seconds.
    type : str
        The action type after timeout: Warning | Blocking
        - Warning: It raises a warning when the process exceeds the timeout.
        - Blocking: It terminates the process when it exceeds the timeout.
    """

    TYPE_WARNING = "Warning"
    TYPE_BLOCKING = "Blocking"

    def __init__(self, timeout, handler_type = "Warning") -> None:
        self.timeout = timeout
        self.type = handler_type
        if self.type not in [TimeoutHandler.TYPE_WARNING, TimeoutHandler.TYPE_BLOCKING]:
            raise ValueError("Invalid timeout type")

    def timeout_handler(self, process, stop_flag):
        """
        Thread function for raising a warning or terminating a process after timeout seconds.
        
        Parameters
        ----------
        process : multiprocessing.Process
            The process to monitor for timeout.
        stop_flag : threading.Event
            Event object to signal the thread to stop.
        """

        stop_flag.wait(self.timeout)

        if process.poll() is None:
            if self.type == TimeoutHandler.TYPE_WARNING:
                print(f"Master process exceeded soft timeout limit after {self.timeout} seconds.")
            else:
                print(f"Master process exceeded timeout limit after {self.timeout} seconds. Terminating ...")
                process.terminate()
