# Define your report URLs here using a clear dictionary structure
REPORT_URLS = {
    "FAF001 - Sales Report": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF001.aspx',
    "FAF002 - Dosage Report": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF002.aspx',
    "FAF003 - Report Of Other Imports And Exports": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF003.aspx',
    "FAF004N - Internal Rotation Report (Imports)": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF004.aspx',
    "FAF004X - Internal Rotation Report (Exports)": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF004.aspx', # Same URL as 4N? Verify.
    "FAF005 - Detailed Report Of Imports": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF005.aspx',
    "FAF006 - Supplier Return Report": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF006.aspx',
    "FAF028 - Detailed Import - Export Transaction Report": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF028.aspx',
    "FAF030 - FAF Inventory Report": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF030.aspx',
    # Add other known reports here for completeness
    # "FAF010 - ???": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF010.aspx',
    # "FAF033 - ???": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF033.aspx',
    # "PHAR043 - ???": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR043.aspx',
    # "PHAR157 - ???": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR157.aspx',
    # "PHAR075 - ???": 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR075.aspx',
}

def get_report_url(report_type=None):
    """
    Returns the URL for a given report type name, or the entire dictionary if no type is specified.

    Args:
        report_type (str, optional): The name of the report (key in REPORT_URLS). Defaults to None.

    Returns:
        str or dict or None: The URL string if report_type is found,
                             the entire REPORT_URLS dictionary if report_type is None,
                             None if report_type is not found.
    """
    if report_type:
        return REPORT_URLS.get(report_type) # .get() returns None if key not found
    return REPORT_URLS

link001 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF001.aspx'
link002 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF002.aspx'
link003 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF003.aspx'
link004 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF004.aspx'
link005 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF005.aspx'
link006 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF006.aspx'
link010 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF010.aspx'
link028 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF028.aspx'
link030 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF030.aspx'
link033 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF033.aspx'
link043 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR043.aspx'
link157 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR157.aspx'
link075 = 'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHAR075.aspx'