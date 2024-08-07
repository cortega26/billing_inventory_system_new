import xlsxwriter
from datetime import datetime
from typing import List, Dict, Any, Iterable
import os
import logging
from utils.decorators import handle_external_service, validate_input
from utils.exceptions import ExternalServiceException, ValidationException

logger = logging.getLogger(__name__)


class ExcelExporter:
    @staticmethod
    @handle_external_service(show_dialog=True)
    @validate_input(show_dialog=True)
    def export_to_excel(
        data: List[Dict[str, Any]],
        headers: List[str],
        filename: str,
        sheet_name: str = "Sheet1",
        auto_adjust_columns: bool = True,
    ) -> None:
        """
        Export data to an Excel file.

        Args:
            data (List[Dict[str, Any]]): The data to be exported. Each dictionary represents a row.
            headers (List[str]): The column headers for the Excel file.
            filename (str): The name of the file to be created (including path).
            sheet_name (str, optional): Name of the worksheet. Defaults to "Sheet1".
            auto_adjust_columns (bool, optional): Whether to auto-adjust column widths. Defaults to True.

        Raises:
            ValidationException: If the data is empty or headers don't match the data.
            ExternalServiceException: If there's an issue writing to the file.
        """
        if not data:
            raise ValidationException("No data to export")

        if set(headers) != set(data[0].keys()):
            raise ValidationException("Headers don't match the data keys")

        try:
            with xlsxwriter.Workbook(filename) as workbook:
                worksheet = workbook.add_worksheet(sheet_name)

                # Define styles
                header_format = workbook.add_format(
                    {"bold": True, "bg_color": "#D3D3D3"}
                )
                date_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})

                # Add headers
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header, header_format)

                # Add data
                for row, item in enumerate(data, start=1):
                    for col, (key, value) in enumerate(item.items()):
                        if isinstance(value, datetime):
                            worksheet.write_datetime(row, col, value, date_format)
                        else:
                            worksheet.write(row, col, value)

                if auto_adjust_columns:
                    for col, header in enumerate(headers):
                        max_width = max(len(str(item[header])) for item in data)
                        worksheet.set_column(col, col, max(len(header), max_width) + 2)

            logger.info(f"Excel file created successfully: {os.path.abspath(filename)}")
        except IOError as e:
            raise ExternalServiceException(
                f"Error writing to file {filename}: {str(e)}"
            )
        except Exception as e:
            raise ExternalServiceException(
                f"An error occurred while exporting to Excel: {str(e)}"
            )

    @staticmethod
    @handle_external_service(show_dialog=True)
    @validate_input(show_dialog=True)
    def export_large_dataset(
        data_generator: Iterable[Dict[str, Any]],
        headers: List[str],
        filename: str,
        sheet_name: str = "Sheet1",
        chunk_size: int = 1000,
    ) -> None:
        """
        Export a large dataset to Excel file using a generator to conserve memory.

        Args:
            data_generator (Iterable[Dict[str, Any]]): A generator that yields dictionaries representing rows.
            headers (List[str]): The column headers for the Excel file.
            filename (str): The name of the file to be created (including path).
            sheet_name (str, optional): Name of the worksheet. Defaults to "Sheet1".
            chunk_size (int, optional): Number of rows to write at a time. Defaults to 1000.

        Raises:
            ExternalServiceException: If there's an issue writing to the file.
        """
        try:
            with xlsxwriter.Workbook(filename) as workbook:
                worksheet = workbook.add_worksheet(sheet_name)

                # Define styles
                header_format = workbook.add_format(
                    {"bold": True, "bg_color": "#D3D3D3"}
                )
                date_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})

                # Add headers
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header, header_format)

                row = 1
                for item in data_generator:
                    for col, (key, value) in enumerate(item.items()):
                        if isinstance(value, datetime):
                            worksheet.write_datetime(row, col, value, date_format)
                        else:
                            worksheet.write(row, col, value)
                    row += 1

                    if row % chunk_size == 0:
                        logger.info(f"Exported {row} rows...")

            logger.info(
                f"Large dataset exported successfully: {os.path.abspath(filename)}"
            )
        except IOError as e:
            raise ExternalServiceException(
                f"Error writing to file {filename}: {str(e)}"
            )
        except Exception as e:
            raise ExternalServiceException(
                f"An error occurred while exporting large dataset to Excel: {str(e)}"
            )
