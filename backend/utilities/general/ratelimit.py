# @Author: Bi Ying
# @Date:   2024-04-30 16:26:47
import time
import threading
from collections import defaultdict, deque

# 使用defaultdict来存储每个产品的请求时间戳队列
# Use defaultdict to store the request timestamp queue for each product
request_records = defaultdict(deque)
lock = threading.Lock()


def add_request_record(product: str, cycle: int = 60) -> bool:
    """
    向内存中添加对特定产品的请求记录。
    Add a request record for a specific product to memory.
    """
    current_time = time.time()

    with lock:
        # 为特定产品添加当前时间戳到队列
        # Add the current timestamp to the queue for the specific product
        request_records[product].append(current_time)
        # 清理超过周期的旧记录
        # Clean up old records that exceed the cycle
        while request_records[product] and request_records[product][0] < current_time - cycle:
            request_records[product].popleft()

        if len(request_records[product]) > 0:
            threading.Timer(interval=cycle, function=clear_expired_records, args=[product, cycle]).start()
        return True


def clear_expired_records(product: str, cycle: int = 60):
    """
    清理指定产品的过期请求记录。
    Clear the expired request records for the specified product.
    """
    current_time = time.time()
    with lock:
        while request_records[product] and request_records[product][0] < current_time - cycle:
            request_records[product].popleft()
        if not request_records[product]:
            request_records[product].clear()


def is_request_allowed(product: str, cycle: int, max_count: int, add_record: bool = False) -> bool:
    """
    检查是否允许请求特定产品。
    Check if it is allowed to request a specific product.
    """
    current_time = time.time()

    with lock:
        # 清理超过周期的旧记录
        # Clean up old records that exceed the cycle
        while request_records[product] and request_records[product][0] < current_time - cycle:
            request_records[product].popleft()

        # 检查当前的请求次数是否超过了允许的最大次数
        # Check if the current number of requests exceeds the maximum allowed
        if len(request_records[product]) >= max_count:
            return False

        if add_record:
            request_records[product].append(current_time)
            threading.Timer(cycle, clear_expired_records, [product, cycle]).start()
        return True


if __name__ == "__main__":
    product = "test_product"
    cycle = 10
    max_count = 6
    for i in range(10):
        print(i + 1, is_request_allowed(product, cycle, max_count, add_record=True))
        time.sleep(1)
    print("Sleeping for 5 seconds...")
    time.sleep(5)
    print("After 5 seconds, the requests are allowed:")
    for i in range(10):
        print(i + 1, is_request_allowed(product, cycle, max_count, add_record=True))
        time.sleep(1)
