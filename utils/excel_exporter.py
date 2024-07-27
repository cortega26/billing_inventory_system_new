import xlsxwriter
from datetime import datetime

class ExcelExporter:
    @staticmethod
    def export_to_excel(data, headers, filename):
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()

        # Add headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)

        # Add data
        for row, item in enumerate(data, start=1):
            for col, (key, value) in enumerate(item.items()):
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                worksheet.write(row, col, value)

        workbook.close()