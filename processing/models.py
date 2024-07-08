from django.db import models


class Request(models.Model):
    request_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, default='Pending')
    webhook_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Product(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE)
    serial_number = models.IntegerField()
    product_name = models.CharField(max_length=255)
    input_image_urls = models.TextField()
    output_image_urls = models.TextField(null=True, blank=True)
