# @Author: Bi Ying
# @Date:   2024-06-07 16:16:49
import time
from typing import Optional, Any, Callable, Tuple, Union, TypeVar, Generic

from .ratelimit import is_request_allowed, add_request_record


ResultType = TypeVar("ResultType")


class Retry(Generic[ResultType]):
    def __init__(self, function: Callable[..., ResultType]):
        self.function: Callable[..., ResultType] = function
        self.__retry_times: int = 3
        self.__sleep_time: Union[int, float] = 1
        self.__rate_limit_args: Optional[Tuple[str, int, int]] = None
        self.__timeout: int = 180
        self.__result_check: Optional[Callable[[ResultType], bool]] = None
        self.pargs: list = []
        self.kwargs: dict = {}

    def args(self, *args: Any, **kwargs: Any) -> "Retry[ResultType]":
        self.pargs = list(args)
        self.kwargs = kwargs
        return self

    def retry_times(self, retry_times: int) -> "Retry[ResultType]":
        self.__retry_times = retry_times
        return self

    def sleep_time(self, sleep_time: Union[int, float]) -> "Retry[ResultType]":
        self.__sleep_time = sleep_time
        return self

    def rate_limit(self, product: str, cycle: int, max_count: int) -> "Retry[ResultType]":
        self.__rate_limit_args = (product, cycle, max_count)
        return self

    def result_check(self, check_function: Callable[[ResultType], bool]) -> "Retry[ResultType]":
        self.__result_check = check_function
        return self

    def _check_result(self, result: ResultType) -> bool:
        try:
            if self.__result_check is None:
                return True
            return self.__result_check(result)
        except Exception as e:
            print(f"Retry result check error: {e}")
            return False

    def run(self) -> Tuple[bool, Optional[ResultType]]:
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
                result: ResultType = self.function(*self.pargs, **self.kwargs)
                if self._check_result(result):
                    return True, result
                try_times += 1
                time.sleep(self.__sleep_time)
            except Exception as e:
                print(f"{self.function.__name__} function error: {e}")
                try_times += 1
                time.sleep(self.__sleep_time)

        return False, None
