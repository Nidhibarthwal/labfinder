import csv
from apps.utility.models import Department, Discipline  # Aapke models path ke mutabiq


def import_lims_masters(file_path):
  with open(file_path, mode='r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    for row in reader:
      disc_name = row['discipline_name'].strip()
      disc_code = row['discipline_code'].strip()
      dept_name = row['department_name'].strip()
      dept_code = row['department_code'].strip()
      dept_type = row['department_type'].strip()

      # 1. Get or create Discipline
      discipline, _ = Discipline.objects.get_or_create(
          name=disc_name, defaults={'code': disc_code, 'is_active': True}
      )

      # 2. Get or create Department linked to Discipline
      Department.objects.get_or_create(
          name=dept_name,
          discipline=discipline,
          defaults={'code': dept_code, 'department_type': dept_type},
      )
  print('LIMS Disciplines and Departments imported successfully!')