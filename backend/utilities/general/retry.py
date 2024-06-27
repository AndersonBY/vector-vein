# @Author: Bi Ying
# @Date:   2024-06-07 16:16:49
import time

from .ratelimit import is_request_allowed, add_request_record


class Retry:
    def __init__(self, function):
        self.function = function
        self.__retry_times = 3
        self.__sleep_time = 1
        self.__rate_limit_args = None
        self.__timeout = 180
        self.pargs = []
        self.kwargs = {}

    def args(self, *args, **kwargs):
        self.pargs = args
        self.kwargs = kwargs
        return self

    def retry_times(self, retry_times: int):
        self.__retry_times = retry_times
        return self

    def sleep_time(self, sleep_time):
        self.__sleep_time = sleep_time
        return self

    def rate_limit(self, product: str, cycle: int, max_count: int):
        self.__rate_limit_args = (product, cycle, max_count)
        return self

    def run(self) -> tuple[bool, any]:
        try_times = 0
        start_time = time.time()

        while try_times <= self.__retry_times and time.time() - start_time < self.__timeout:
            if self.__rate_limit_args is not None:
                product, cycle, max_count = self.__rate_limit_args
                if not is_request_allowed(product, cycle, max_count):
                    print(f"<{product}> has reached the request limit, waiting for {self.__sleep_time} seconds...")
                    if time.time() - start_time > self.__timeout:
                        print(f"Failed to request within {self.__timeout} seconds due to reaching the request limit.")
                        return False, None
                    time.sleep(self.__sleep_time)
                    continue

            try:
                if self.__rate_limit_args is not None:
                    product, cycle, _ = self.__rate_limit_args
                    add_request_record(product, cycle)
                return True, self.function(*self.pargs, **self.kwargs)
            except Exception as e:
                print(f"{self.function.__name__} function error: {e}")
                try_times += 1
                time.sleep(self.__sleep_time)

        return False, None
