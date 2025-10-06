#!/usr/bin/env python3
"""
Network Testing Automation Tool for Industrial Systems
Performs ICMP ping tests on multiple target devices with structured JSON output.
"""

import argparse
import json
import logging
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re


class NetworkTester:
    def __init__(self, retry_count: int = 3, retry_interval: float = 1.0, 
                 log_level: str = "INFO"):
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.results = {}
        self.lock = threading.Lock()
        
        # Setup logging
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("network_test.log", mode='a')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _get_ping_command(self, target: str, count: int = 1) -> List[str]:
        """Generate appropriate ping command based on OS."""
        system = platform.system().lower()
        
        if system == "windows":
            return ["ping", "-n", str(count), target]
        else:  # Linux, macOS, Unix-like
            return ["ping", "-c", str(count), target]
    
    def _parse_ping_output(self, output: str, target: str) -> Optional[float]:
        """Parse ping output to extract RTT in milliseconds."""
        try:
            system = platform.system().lower()

            if system == "windows":
                match = re.search(r'[=<](\d+)ms', output)
                if match:
                    return float(match.group(1))
            else:
                # Unix-like systems ping output pattern
                match = re.search(r'time=(\d+\.?\d*)', output)
                if match:
                    return float(match.group(1))
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing ping output for {target}: {e}")
            return None
    
    def _single_ping(self, target: str) -> Optional[float]:
        """Perform a single ping test and return RTT or None if failed."""
        for attempt in range(self.retry_count):
            try:
                cmd = self._get_ping_command(target, 1)
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                # 加入詳細的除錯資訊
                self.logger.debug(f"Command: {' '.join(cmd)}")
                self.logger.debug(f"Return code: {result.returncode}")
                self.logger.debug(f"STDOUT: {result.stdout[:200]}")  # 只顯示前200字元
                self.logger.debug(f"STDERR: {result.stderr[:200]}")

                if result.returncode == 0:
                    rtt = self._parse_ping_output(result.stdout, target)
                    if rtt is not None:
                        return rtt
                    else:
                        self.logger.warning(f"Ping succeeded but failed to parse output for {target}")
            
                
                # Log failure details
                error_msg = result.stderr if result.stderr else f"Return code: {result.returncode}, stdout: {result.stdout[:100]}"
                self.logger.warning(f"Ping attempt {attempt + 1} failed for {target}: {error_msg}")

                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_interval)
                    
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Ping timeout for {target} on attempt {attempt + 1}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_interval)
            except Exception as e:
                self.logger.error(f"Ping error for {target} on attempt {attempt + 1}: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_interval)
        
        self.logger.error(f"All ping attempts failed for {target}")
        return None
    
    def _test_device(self, target: str, duration: int, rate: int):
        """Test a single device for the specified duration and rate."""
        self.logger.info(f"Starting ping test for {target}")
        
        device_results = {
            "RTT_samples": [],
            "RTT_avg": "0ms",
            "RTT_max": "0ms",
            "packet_loss": "0%"
        }
        
        interval = 1.0 / rate  # Calculate interval between pings
        end_time = time.time() + duration
        total_attempts = 0
        failed_attempts = 0
        
        while time.time() < end_time:
            start_ping = time.time()
            rtt = self._single_ping(target)
            total_attempts += 1
            
            if rtt is not None:
                device_results["RTT_samples"].append(int(round(rtt)))
            else:
                failed_attempts += 1
                self.logger.warning(f"Packet loss detected for {target} at {datetime.now()}")
            
            # Calculate sleep time to maintain rate
            elapsed = time.time() - start_ping
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Calculate statistics
        if device_results["RTT_samples"]:
            samples = device_results["RTT_samples"]
            device_results["RTT_avg"] = f"{sum(samples) / len(samples):.0f}ms"
            device_results["RTT_max"] = f"{max(samples):.0f}ms"
        
        # Calculate packet loss
        if total_attempts > 0:
            loss_percentage = (failed_attempts / total_attempts) * 100
            device_results["packet_loss"] = f"{loss_percentage:.0f}%"
        
        # Thread-safe result storage
        with self.lock:
            self.results[target] = device_results
        
        self.logger.info(f"Completed ping test for {target}")
    
    def run_tests(self, targets: List[str], duration: int, rate: int) -> Dict:
        """Run network tests on multiple targets."""
        self.logger.info(f"Starting network tests for {len(targets)} targets")
        start_time = datetime.now()
        
        # Initialize results structure
        test_results = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": "",
            "rate": f"{rate} packets/sec",
            "results": {}
        }
        
        # Create and start threads for each target
        threads = []
        for target in targets:
            thread = threading.Thread(
                target=self._test_device,
                args=(target, duration, rate)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Finalize results
        end_time = datetime.now()
        test_results["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")

        # Only keep first 4 RTT samples for brevity
        for target in targets:
            if target in self.results:
                data = self.results[target].copy()
                data["RTT_samples"] = data["RTT_samples"][:4]
                test_results["results"][target] = data
        
        self.logger.info(f"Network tests completed for all {len(targets)} targets")
        return test_results


def main():
    parser = argparse.ArgumentParser(
        description="Network Testing Automation Tool for Industrial Systems"
    )
    
    parser.add_argument(
        "--targets",
        nargs="+",
        required=True,
        help="Target IP addresses to test"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--rate",
        type=int,
        default=1,
        help="Ping rate in packets per second (default: 1)"
    )
    
    parser.add_argument(
        "--retry-count",
        type=int,
        default=3,
        help="Number of retry attempts for failed pings (default: 3)"
    )
    
    parser.add_argument(
        "--retry-interval",
        type=float,
        default=1.0,
        help="Interval between retry attempts in seconds (default: 1.0)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.duration <= 0:
        print("Error: Duration must be positive")
        sys.exit(1)
    
    if args.rate <= 0:
        print("Error: Rate must be positive")
        sys.exit(1)
    
    if args.retry_count < 1:
        print("Error: Retry count must be at least 1")
        sys.exit(1)
    
    # Create tester instance
    tester = NetworkTester(
        retry_count=args.retry_count,
        retry_interval=args.retry_interval,
        log_level=args.log_level
    )
    
    try:
        # Run tests
        results = tester.run_tests(args.targets, args.duration, args.rate)
        
        # Output results
        json_output = json.dumps(results, indent=4)

        json_output = re.sub(
            r'"RTT_samples":\s*\[\s*((?:\d+,?\s*)+)\s*\]',
            lambda m: f'"RTT_samples": [{", ".join(m.group(1).replace(",", "").split())}]',
            json_output,
            flags=re.DOTALL
        )

        print(json_output)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during testing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()