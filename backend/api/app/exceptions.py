class SummarizationStatusCodeError(Exception):
    """Exception raised because audio-ml service returned something beside 200 status code"""
    pass

class SummarizationJSONParseException(Exception):
    """Exception raised because audio-ml service returned wrong JSON format"""
    pass
