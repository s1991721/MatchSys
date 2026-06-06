from enum import Enum


SUCCESS_CODE = 0


class ErrorCode(Enum):
    # Common/request/auth: 100xxx
    INVALID_REQUEST = (100000, "Invalid request")
    INVALID_JSON = (100001, "Invalid JSON body")
    INVALID_DATE = (100002, "Invalid date")
    INVALID_TIME = (100003, "Invalid time")
    LOGIN_REQUIRED = (100401, "Login required")
    LOGIN_INVALID_CREDENTIALS = (100402, "Invalid credentials")
    FORBIDDEN = (100403, "Forbidden")
    METHOD_NOT_ALLOWED = (100405, "Method not allowed")
    LOGIN_PASSWORD_EXPIRED = (100406, "Password expired")
    PASSWORD_CHANGE_FIELDS_REQUIRED = (100407, "Missing old_password or new_password")
    PASSWORD_NEW_SAME_AS_OLD = (100408, "New password must be different")
    PASSWORD_CURRENT_INVALID = (100409, "Invalid current password")
    ACTIVATION_REQUIRED = (100410, "Activation required")
    SERVER = (100500, "Internal server error")

    # File upload/read: 101xxx
    FILE_MISSING = (101001, "Missing file")
    FILE_NOT_FOUND = (101003, "File not found")
    FILE_PATH_INVALID = (101004, "Invalid file path")
    FILE_TYPE_INVALID = (101005, "Invalid file type")

    # Customer: 200xxx
    CUSTOMER_NOT_FOUND = (200001, "Customer not found")
    CUSTOMER_COMPANY_NAME_REQUIRED = (200002, "Customer company_name is required")
    CUSTOMER_CONTRACT_FILE_REQUIRED = (200003, "Customer contract file is required")
    CUSTOMER_CARD_FILE_REQUIRED = (200004, "Customer card file is required")
    CUSTOMER_CARD_OCR_FAILED = (200005, "Customer card OCR failed")
    CUSTOMER_LINE_SECRET_REQUIRED = (200006, "LINE channel secret is required")
    CUSTOMER_LINE_SIGNATURE_INVALID = (200007, "Invalid LINE signature")

    # Employee/personnel/technician: 300xxx
    EMPLOYEE_NOT_FOUND = (300001, "Employee not found")
    EMPLOYEE_ID_INVALID = (300002, "Invalid employee_id")
    EMPLOYEE_ID_REQUIRED = (300003, "Employee ID is required")
    EMPLOYEE_ID_DUPLICATE = (300004, "Employee ID already exists")
    EMPLOYEE_NAME_REQUIRED = (300005, "Employee name is required")
    EMPLOYEE_NAME_MASK_REQUIRED = (300006, "Employee name_mask is required")
    EMPLOYEE_BIRTHDAY_REQUIRED = (300007, "Employee birthday is required")
    EMPLOYEE_NATIONALITY_INVALID = (300008, "Invalid nationality")
    EMPLOYEE_EMAIL_REQUIRED = (300009, "Employee email is required")
    EMPLOYEE_LOGIN_AUDIT_SUCCESS_INVALID = (300010, "Invalid success")
    TECHNICIAN_NOT_FOUND = (300101, "Technician not found")
    TECHNICIAN_NAME_REQUIRED = (300102, "Technician name is required")
    USER_LOGIN_NOT_FOUND = (300201, "User login not found")
    USER_NAME_PASSWORD_REQUIRED = (300202, "User name or password is required")
    USER_LOGIN_ALREADY_EXISTS = (300203, "User login already exists")
    USER_NOT_FOUND = (300204, "User not found")
    ROLE_ID_INVALID = (300301, "Invalid role_id")
    ROLE_ID_REQUIRED = (300302, "Role ID is required")

    # Permission: 310xxx
    PERMISSION_MENU_NOT_FOUND = (310001, "Menu not found")
    PERMISSION_MENU_NAME_REQUIRED = (310002, "Menu name is required")
    PERMISSION_MENU_HTML_REQUIRED = (310003, "Menu html is required")
    PERMISSION_ROLE_NOT_FOUND = (310101, "Role not found")
    PERMISSION_ROLE_NAME_REQUIRED = (310102, "Role name is required")

    # Attendance: 320xxx
    ATTENDANCE_DATE_REQUIRED = (320001, "Attendance date is required")
    ATTENDANCE_DATE_INVALID = (320002, "Invalid attendance date")
    ATTENDANCE_REMARK_REQUIRED = (320003, "Attendance remark is required")
    ATTENDANCE_TIME_RANGE_REQUIRED = (320004, "Attendance start_time or end_time is required")
    ATTENDANCE_MONTH_REQUIRED = (320005, "Attendance month is required")
    ATTENDANCE_EXPORT_FAILED = (320006, "Attendance export failed")
    ATTENDANCE_TEMPLATE_NOT_FOUND = (320007, "Attendance template not found")
    ATTENDANCE_TEMPLATE_SHEET_NOT_FOUND = (320008, "Attendance template sheet not found")
    ATTENDANCE_YEAR_TEMPLATE_FAILED = (320009, "Attendance year template generation failed")

    # Order/pay request: 400xxx
    ORDER_LOCKED = (400002, "Order is locked")
    ORDER_STATUS_INVALID = (400003, "Invalid order status")
    ORDER_CUSTOMER_ID_INVALID = (400004, "Invalid order customer_id")
    ORDER_PERSON_IN_CHARGE_REQUIRED = (400005, "Order person_in_charge is required")
    ORDER_PERSON_IN_CHARGE_ID_INVALID = (400006, "Invalid order person_in_charge_id")
    ORDER_LINE_ITEMS_REQUIRED = (400007, "Order line_items is required")
    ORDER_LINE_ITEMS_INVALID_JSON = (400008, "Invalid JSON: order line_items")
    ORDER_LINE_ITEM_PURCHASE_ID_REQUIRED = (400009, "Order line item purchase_id is required")
    ORDER_LINE_ITEM_TECHNICIAN_NAME_REQUIRED = (400010, "Order line item technician_name is required")
    ORDER_PURCHASE_ID_INVALID = (400011, "Invalid order purchase_id")
    ORDER_TECHNICIAN_ID_INVALID = (400012, "Invalid order technician_id")
    ORDER_PRICE_INVALID = (400013, "Invalid order price")
    ORDER_PDF_REQUIRED = (400014, "Order PDF file is required")
    ORDER_PDF_INVALID = (400015, "Invalid order PDF file")
    ORDER_DETAILS_INVALID_JSON = (400016, "Invalid JSON: order details")
    ORDER_INVALID_CUSTOMER_ID = (400021, "Invalid customer_id")
    PURCHASE_ORDER_NOT_FOUND = (400201, "Purchase order not found")
    SALES_ORDER_NOT_FOUND = (400202, "Sales order not found")
    PAY_REQUEST_NOT_FOUND = (400101, "Pay request not found")
    PAY_REQUEST_DETAILS_REQUIRED = (400102, "Pay request details is required")
    PAY_REQUEST_MONTH_INVALID = (400104, "Invalid pay request month")

    # System settings/tasks/activation/password: 500xxx
    SETTINGS_SECTION_UNKNOWN = (500001, "Unknown settings section")
    SETTINGS_ACTION_UNSUPPORTED = (500002, "Unsupported settings action")
    SETTINGS_PAYLOAD_INVALID = (500003, "Invalid settings payload")
    SETTINGS_FIELD_SETTINGS_REQUIRED = (500004, "Settings field is required")
    SETTINGS_TEMPLATE_REQUIRED = (500005, "Template is required")
    SETTINGS_MODE_INVALID = (500006, "Invalid settings mode")
    SETTINGS_MODEL_NAME_INVALID = (500007, "Invalid settings model name")
    SETTINGS_API_KEY_INVALID = (500008, "Invalid settings API key")
    SETTINGS_CYCLE_DAYS_INVALID = (500009, "Invalid settings cycle_days")
    SETTINGS_GMAIL_FILES_REQUIRED = (500101, "Missing Gmail auth or token file")
    SETTINGS_GMAIL_AUTH_JSON_INVALID = (500102, "Invalid Gmail auth JSON file")
    SETTINGS_GMAIL_TOKEN_JSON_INVALID = (500103, "Invalid Gmail token JSON file")
    SETTINGS_GMAIL_TEST_FAILED = (500104, "Gmail connection test failed")
    SETTINGS_OCR_FILE_REQUIRED = (500201, "Missing OCR auth file")
    SETTINGS_OCR_JSON_INVALID = (500202, "Invalid OCR auth JSON file")
    SETTINGS_TASKS_REQUIRED = (500301, "Tasks field is required")
    SETTINGS_TASK_PAYLOAD_INVALID = (500302, "Invalid task payload")
    SETTINGS_TASK_ID_REQUIRED = (500303, "Missing task_id")
    SETTINGS_TASK_ID_INVALID = (500304, "Invalid task_id")
    SETTINGS_TASK_START_DATE_INVALID = (500305, "Invalid task start_date")
    SETTINGS_TASK_END_DATE_INVALID = (500306, "Invalid task end_date")
    SETTINGS_TASK_DATE_RANGE_INVALID = (500307, "Invalid task date range")
    SETTINGS_ACTIVATION_CODE_REQUIRED = (500401, "Missing activation code")
    SETTINGS_ACTIVATION_CODE_INVALID = (500402, "Invalid or expired activation code")
    SETTINGS_PASSWORD_RESET_USER_PASSWORD_REQUIRED = (500501, "Missing user_name or password")
    SETTINGS_PASSWORD_RESET_EXPIRES_INVALID = (500502, "Invalid expires_in_days")
    SETTINGS_PASSWORD_RESET_EXPIRES_TOO_SMALL = (500503, "expires_in_days must be at least 1")
    SETTINGS_SMTP_CONFIG_REQUIRED = (500601, "Missing SMTP config")
    SETTINGS_SMTP_PORT_INVALID = (500602, "Invalid SMTP port")
    SETTINGS_SENDMSG_TEST_FAILED = (500603, "Send mail config test failed")
    SETTINGS_LINE_TEST_FAILED = (500701, "LINE notification test failed")

    # BP match/mail/history: 600xxx
    MATCH_ID_REQUIRED = (600001, "Missing id")
    MATCH_MAIL_NOT_FOUND = (600002, "Mail not found")
    MATCH_PROJECT_INFO_NOT_FOUND = (600003, "MailProjectInfo not found")
    MATCH_WRONG_LABEL_REQUIRED = (600004, "Missing wrong_label")
    MATCH_WRONG_LABEL_INVALID = (600005, "Invalid wrong_label")
    MATCH_WRONG_TYPE_REQUIRED = (600006, "Missing wrong_type")
    MATCH_WRONG_TYPE_INVALID = (600007, "Invalid wrong_type")
    MATCH_MAIL_TYPE_INVALID = (600008, "Invalid mail_type")
    MATCH_ATTACHMENT_IDS_REQUIRED = (600101, "message_id and attachment_id are required")
    MATCH_ATTACHMENT_NOT_FOUND = (600102, "Attachment not found")

    # External services: 900xxx
    EXTERNAL_GMAIL = (900003, "External Gmail error")
    EXTERNAL_LLM = (900004, "External LLM error")
    EXTERNAL_OPENAI_RESPONSE_FAILED = (900006, "OpenAI response failed")
    EXTERNAL_OPENAI_REQUEST_FAILED = (900007, "OpenAI request failed")

    def __init__(self, code, message):
        self.code = code
        self.message = message
