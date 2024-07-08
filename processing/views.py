from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage
from .models import Request, Product
from .serializers import RequestSerializer
import csv
import uuid
from concurrent.futures import ThreadPoolExecutor
import threading
import requests
from PIL import Image
from io import BytesIO
import boto3

executor = ThreadPoolExecutor(max_workers=10)


def process_images_task(request_id):
    request_instance = Request.objects.get(request_id=request_id)
    products = Product.objects.filter(request=request_instance)

    for product in products:
        input_urls = product.input_image_urls.split(',')
        output_urls = []

        for url in input_urls:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")
            output = BytesIO()
            img.save(output, format="JPEG", quality=50)
            output.seek(0)
            # Logic to upload image into some storage unit like S3
            s3 = boto3.client('s3')
            bucket = 'your-bucket-name'
            key = f'compressed/{product.serial_number}_{url.split("/")[-1]}'
            s3.upload_fileobj(output, bucket, key)
            output_url = f'https://{bucket}.s3.amazonaws.com/{key}'
            output_urls.append(output_url)
            # Logic ends

        product.output_image_urls = ','.join(output_urls)
        product.save()

    request_instance.status = 'Completed'
    request_instance.save()

    if request_instance.webhook_url:
        trigger_webhook(request_instance.webhook_url, request_id)


def trigger_webhook(webhook_url, request_id):
    try:
        requests.post(webhook_url, json={'request_id': request_id, 'status': 'Completed'})
    except requests.exceptions.RequestException as e:
        print(f"Webhook trigger failed: {e}")


class UploadCSV(APIView):
    def post(self, request, format=None):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        file_path = fs.path(filename)

        request_id = str(uuid.uuid4())
        request_instance = Request.objects.create(request_id=request_id)

        with open(file_path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)
            for row in reader:
                serial_number, product_name, input_image_urls = row
                Product.objects.create(
                    request=request_instance,
                    serial_number=serial_number,
                    product_name=product_name,
                    input_image_urls=input_image_urls,
                )

        executor.submit(process_images_task, request_id)

        return Response({'request_id': request_id}, status=status.HTTP_200_OK)


class CheckStatus(APIView):
    def get(self, request, request_id, format=None):
        try:
            request_instance = Request.objects.get(request_id=request_id)
            serializer = RequestSerializer(request_instance)
            print(threading.active_count())
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Request.DoesNotExist:
            return Response({'error': 'Invalid request ID'}, status=status.HTTP_404_NOT_FOUND)
