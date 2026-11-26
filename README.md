# Electronics Lab Equipment Loan API (Track C)

Serverless REST API untuk mencatat inventaris dan peminjaman alat laboratorium elektronika (*equipment loans*), yang dibangun menggunakan **AWS**.

## Arsitektur

```
Client (curl / Postman)
   │ HTTPS
   ▼
AWS Lambda Function URL (HTTPS, Auth: NONE)
   │ Invoke (HTTP payload v2.0)
   ▼
AWS Lambda — lab-equipment-handler (Python 3.12, Reserved Concurrency: 5)
   ├── IAM LabRole (execution role, tanpa hardcoded credentials)
   ├── Amazon S3 — lab-equipment-data (equipment/<id>.json, Block Public Access: ON)
   └── Amazon CloudWatch Logs (/aws/lambda/lab-equipment-handler)
```

## Struktur Repositori

```
.
├── lambda/
│   └── lambda_function.py   # Handler CRUD & validasi (Python 3.12 + boto3 S3)
├── deploy/
│   └── deploy.sh            # Skrip AWS CLI reproducible untuk rebuild di sandbox
├── tests/
│   └── test-api.sh          # Skrip uji curl untuk seluruh alur CRUD
├── .gitignore
└── README.md
```

## Entitas Data (`Equipment`)

Disimpan di S3 sebagai `equipment/<id>.json` dengan atribut:
`id` (UUID v4), `name`, `category` (`microcontroller` | `sensor` | `measurement` | `power` | `component` | `tool`), `assetTag`, `condition` (`good` | `fair` | `damaged`), `status` (`available` | `borrowed` | `maintenance`), `borrower`, `dueDate`, `createdAt`.

## Endpoint CRUD (4 Operasi, 5 Route)

| Operasi | Method | Path | Operasi S3 |
|---|---|---|---|
| Create | `POST` | `/equipment` | `PutObject` |
| Read (all) | `GET` | `/equipment` | `ListObjectsV2` + `GetObject` |
| Read (one) | `GET` | `/equipment/{id}` | `GetObject` |
| Update | `PUT` | `/equipment/{id}` | `GetObject` + `PutObject` |
| Delete | `DELETE` | `/equipment/{id}` | `DeleteObject` |

## Deployment Plan

Terdapat reproducible code untuk membuat melakukan deployment kembali apabila diperlukan yakni [deploy/deploy.sh](deploy/deploy.sh):

1. Mulai sesi AWS Sandbox dan buka **AWS CloudShell** atau **VS Code Lab IDE** di region `us-east-1`.
2. Clone repositori dan jalankan skrip deploy:
   ```bash
   git clone https://github.com/nathanaelputratz/534424-Track-C-Cloud-Computing.git
   cd 534424-Track-C-Cloud-Computing
   ./deploy/deploy.sh
   ```
3. Skrip otomatis melakukan:
   - Membuat bucket S3 `lab-equipment-data` dengan *Block all public access* aktif.
   - Mem-package `lambda/lambda_function.py` dan membuat/memperbarui Lambda `lab-equipment-handler` (`Python 3.12`, `LabRole`, timeout 10s, env `BUCKET_NAME=lab-equipment-data`).
   - Mengatur *Reserved Concurrency* (`5`) sebagai pembatasan beban ringan.
   - Mengaktifkan **Lambda Function URL** (`AuthType: NONE`) dan mencetak URL siap pakai.

## Pengujian

Pengujian script CRUD dapat menggunakan Function URL hasil deploy dengan script dibawah ini:

```bash
./tests/test-api.sh https://<url-id>.lambda-url.us-east-1.on.aws
```