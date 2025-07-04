
import time

def cpu_intensive_task(n=10000000):
    print("Starting CPU-intensive task...")
    total = 0
    for i in range(1, n):
        total += i ** 0.5
    print("CPU task done.")
    return total



def main():
    start_time = time.time()
    cpu_intensive_task()
    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()