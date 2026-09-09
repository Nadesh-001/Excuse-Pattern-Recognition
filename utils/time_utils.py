from datetime import datetime

def calculate_elapsed_time(created_at):
    """
    Calculates the elapsed time from created_at to now.
    Returns a string like '5d 21h 35m'.
    """
    if not created_at:
        return "N/A"
        
    if isinstance(created_at, str):
        try:
            created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return "N/A"
            
    now = datetime.now()
    # Handle timezone-aware datetimes from PostgreSQL
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
        
    delta = now - created_at
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
        
    return " ".join(parts) if parts else "0m"

def parse_time_input(hours, minutes):
    """
    Converts hours and minutes strings/ints to total minutes integer.
    """
    try:
        h = int(hours or 0)
        m = int(minutes or 0)
        return (h * 60) + m
    except (ValueError, TypeError):
        return 0
