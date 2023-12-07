import time
import sys

def sleep():
    """Sleep forever seconds"""
    while True:
        time.sleep(1)

def run():
    """Process all template files"""
    print("Running!")

def main():
    """DSCN entry point"""
    try:
        task = sys.argv[1]
    except IndexError:
        print("Usage: dscn <sleep|decrypt>")
        sys.exit(1)

    if task == "sleep":
        try:
            sleep()
        except KeyboardInterrupt:
            print("Exiting...")
            sys.exit(0)
    elif task == "decrypt":
        run()
    else:
        print("Usage: dscn <sleep|decrypt>")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Unexpected error: {}".format(e))
        sys.exit(1)
    else:
        sys.exit(0)
