def bin_search(lst, val):
    """Binary search for descending list; return insertion index."""
    left, right = 0, len(lst) - 1
    while left <= right:
        mid = (left + right) // 2
        if lst[mid] == val:
            return mid
        elif lst[mid] > val:
            left = mid + 1   # go right because values decrease
        else:
            right = mid - 1
    return left
