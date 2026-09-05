from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.analysis_result import AnalysisResult
from app.models.inspection import Inspection
from app.models.product import Product
from app.schemas.consumer import (
    ConsumerDeclarationItem,
    ConsumerProductDetail,
    ConsumerProductSummary,
    ConsumerQualityInfo,
    ConsumerScanResponse,
)
from app.services.ocr_service import OCRService
from app.services.quality_service import assess_image_quality

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/consumer', tags=['Consumer Mode'])

CONSUMER_LEGAL_NOTICE = (
    "This is an informational packaging transparency tool under the Legal Metrology "
    "(Packaged Commodities) Rules, 2011. A declaration 'Not detected in this image' does not "
    "mean it is legally absent from the package, as it may appear on other panels or sides. "
    "This scan does not constitute an official inspection result, statutory non-compliance finding, "
    "or enforcement order."
)


@router.get('/products', response_model=List[ConsumerProductSummary])
def list_consumer_products(
    search: Optional[str] = Query(None, description="Search by product name, brand, or manufacturer"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
) -> List[ConsumerProductSummary]:
    """
    Public, sanitized product catalog listing for consumers.
    Strictly excludes internal inspection metrics, scores, and review decisions.
    """
    query = db.query(Product)
    if category and category.strip():
        query = query.filter(Product.category.ilike(f"%{category.strip()}%"))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            Product.name.ilike(term)
            | Product.brand.ilike(term)
            | Product.manufacturer.ilike(term)
        )

    products = query.order_by(Product.name.asc()).limit(100).all()

    return [
        ConsumerProductSummary(
            id=p.id,
            name=p.name,
            brand=p.brand,
            category=p.category,
            manufacturer=p.manufacturer,
            description=p.description,
        )
        for p in products
    ]


@router.get('/products/{product_id}', response_model=ConsumerProductDetail)
def get_consumer_product_detail(
    product_id: str,
    db: Session = Depends(get_db),
) -> ConsumerProductDetail:
    """
    Public consumer product details including known packaging declarations.
    Excludes all internal inspection IDs, findings, review decisions, and officer data.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in public catalog",
        )

    # Check if any inspection has extracted declarations for this product
    latest_analysis = (
        db.query(AnalysisResult)
        .join(Inspection, AnalysisResult.inspection_id == Inspection.id)
        .filter(Inspection.product_id == product.id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )

    declarations: List[ConsumerDeclarationItem] = []
    extracted = latest_analysis.structured_declarations if latest_analysis and latest_analysis.structured_declarations else {}

    # 1. Commodity Name
    comm_name = extracted.get('commodity_name') or product.name
    declarations.append(
        ConsumerDeclarationItem(
            field_key="commodity_name",
            field_label="Commodity / Product Name",
            status="Detected" if comm_name else "Not applicable / unknown",
            detected_value=comm_name,
            description="Identification of the commodity contained in the package.",
        )
    )

    # 2. Net Quantity
    net_qty = extracted.get('net_quantity')
    qty_unit = extracted.get('quantity_unit')
    net_qty_val = f"{net_qty} {qty_unit}".strip() if net_qty else None
    declarations.append(
        ConsumerDeclarationItem(
            field_key="net_quantity",
            field_label="Net Quantity",
            status="Detected" if net_qty_val else "Not detected in this image",
            detected_value=net_qty_val,
            description="Weight, measure or numerical count of the commodity in standard metric units.",
        )
    )

    # 3. Maximum Retail Price (MRP)
    mrp = extracted.get('retail_sale_price')
    declarations.append(
        ConsumerDeclarationItem(
            field_key="retail_sale_price",
            field_label="Maximum Retail Price (MRP)",
            status="Detected" if mrp else "Not detected in this image",
            detected_value=f"₹{mrp}" if mrp and not str(mrp).startswith('₹') else mrp,
            description="Retail price inclusive of all taxes. No retailer can charge above this price.",
        )
    )

    # 4. Manufacturer Details
    mfg_name = extracted.get('manufacturer_name') or product.manufacturer
    mfg_addr = extracted.get('manufacturer_address')
    mfg_combined = f"{mfg_name}, {mfg_addr}".strip(', ') if mfg_name or mfg_addr else None
    declarations.append(
        ConsumerDeclarationItem(
            field_key="manufacturer_name_address",
            field_label="Manufacturer / Packer Details",
            status="Detected" if mfg_combined else "Not detected in this image",
            detected_value=mfg_combined,
            description="Name and complete address of the manufacturing, packing, or importing entity.",
        )
    )

    # 5. Consumer Care Contact
    care = extracted.get('consumer_contact')
    declarations.append(
        ConsumerDeclarationItem(
            field_key="consumer_contact",
            field_label="Consumer Care Contact",
            status="Detected" if care else "Not detected in this image",
            detected_value=care,
            description="Contact details (telephone, email, or address) for customer service and grievances.",
        )
    )

    # 6. Month & Year of Packaging
    m_y = extracted.get('month_year')
    declarations.append(
        ConsumerDeclarationItem(
            field_key="month_year",
            field_label="Date / Month & Year of Packing (where applicable)",
            status="Detected" if m_y else "Not detected in this image",
            detected_value=m_y,
            description="Month and year of manufacture or pre-packing (certain commodities have specific statutory exemptions).",
        )
    )

    # 7. Country of Origin
    origin = extracted.get('country_of_origin')
    declarations.append(
        ConsumerDeclarationItem(
            field_key="country_of_origin",
            field_label="Country of Origin (for imported goods)",
            status="Detected" if origin else "Not applicable / unknown",
            detected_value=origin,
            description="Mandatory for imported pre-packaged commodities under Rule 6(10). Domestic goods do not require Country of Origin.",
        )
    )

    return ConsumerProductDetail(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        manufacturer=product.manufacturer,
        description=product.description,
        declarations=declarations,
        consumer_notice=CONSUMER_LEGAL_NOTICE,
    )


@router.post('/scan', response_model=ConsumerScanResponse)
def scan_package_transient(
    file: UploadFile = File(...),
) -> ConsumerScanResponse:
    """
    Transient, public consumer package image scan.
    Runs Image Quality Assessment and OCR declaration extraction in-memory.
    CRITICAL INVARIANT: Zero database records (Inspection, Finding, ReviewDecision) are created.
    """
    filename = file.filename or 'package.jpg'
    ext = Path(filename).suffix.lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Please upload JPG, PNG, or WebP.",
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="praman_consumer_"))
    temp_file = temp_dir / f"scan_{uuid4().hex}{ext}"

    try:
        with open(temp_file, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        # 1. Quality Assessment
        quality_report = assess_image_quality(temp_file)
        is_unreadable = quality_report.quality_verdict == "UNREADABLE"

        quality_info = ConsumerQualityInfo(
            quality_verdict=quality_report.quality_verdict,
            quality_notes=(
                "Image quality is optimal for packaging declaration extraction."
                if quality_report.quality_verdict == "ACCEPTABLE"
                else "Image may have glare or blur, but text extraction was attempted."
                if quality_report.quality_verdict == "WARNING_DEGRADED"
                else "Image is blurry or poorly illuminated. Some declarations may not be detected."
            ),
            is_sufficient_for_scan=not is_unreadable,
        )

        # 2. OCR Extraction
        ocr_result = OCRService.analyze_image(temp_file, inspection_id=f"transient_{uuid4().hex[:8]}")
        extracted = ocr_result.get('structured_declarations', {})

        declarations: List[ConsumerDeclarationItem] = []

        def get_status(value: Optional[str]) -> str:
            if value:
                return "Detected"
            if is_unreadable:
                return "Image quality insufficient"
            return "Not detected in this image"

        # 1. Commodity Name
        comm = extracted.get('commodity_name')
        declarations.append(
            ConsumerDeclarationItem(
                field_key="commodity_name",
                field_label="Commodity / Product Name",
                status=get_status(comm),
                detected_value=comm,
                description="Identification of the commodity contained in the package.",
            )
        )

        # 2. Net Quantity
        net_q = extracted.get('net_quantity')
        unit = extracted.get('quantity_unit')
        net_str = f"{net_q} {unit}".strip() if net_q else None
        declarations.append(
            ConsumerDeclarationItem(
                field_key="net_quantity",
                field_label="Net Quantity",
                status=get_status(net_str),
                detected_value=net_str,
                description="Weight, measure or numerical count of the commodity in standard metric units.",
            )
        )

        # 3. Maximum Retail Price (MRP)
        mrp = extracted.get('retail_sale_price')
        declarations.append(
            ConsumerDeclarationItem(
                field_key="retail_sale_price",
                field_label="Maximum Retail Price (MRP)",
                status=get_status(mrp),
                detected_value=f"₹{mrp}" if mrp and not str(mrp).startswith('₹') else mrp,
                description="Retail price inclusive of all taxes. No retailer can charge above this price.",
            )
        )

        # 4. Manufacturer / Packer Details
        mfg_name = extracted.get('manufacturer_name')
        mfg_addr = extracted.get('manufacturer_address')
        mfg_combined = f"{mfg_name}, {mfg_addr}".strip(', ') if mfg_name or mfg_addr else None
        declarations.append(
            ConsumerDeclarationItem(
                field_key="manufacturer_name_address",
                field_label="Manufacturer / Packer Details",
                status=get_status(mfg_combined),
                detected_value=mfg_combined,
                description="Name and complete address of the manufacturing, packing, or importing entity.",
            )
        )

        # 5. Consumer Care Contact
        care = extracted.get('consumer_contact')
        declarations.append(
            ConsumerDeclarationItem(
                field_key="consumer_contact",
                field_label="Consumer Care Contact",
                status=get_status(care),
                detected_value=care,
                description="Contact details (telephone, email, or address) for customer service and grievances.",
            )
        )

        # 6. Date / Month & Year of Packing
        my = extracted.get('month_year')
        declarations.append(
            ConsumerDeclarationItem(
                field_key="month_year",
                field_label="Date / Month & Year of Packing (where applicable)",
                status=get_status(my),
                detected_value=my,
                description="Month and year of manufacture or pre-packing (certain commodities have specific statutory exemptions).",
            )
        )

        # 7. Country of Origin (Conditional)
        coo = extracted.get('country_of_origin')
        declarations.append(
            ConsumerDeclarationItem(
                field_key="country_of_origin",
                field_label="Country of Origin (for imported goods)",
                status="Detected" if coo else "Not applicable / unknown",
                detected_value=coo,
                description="Mandatory for imported pre-packaged commodities under Rule 6(10). Domestic goods do not require Country of Origin.",
            )
        )

        return ConsumerScanResponse(
            scan_id=str(uuid4()),
            image_name=filename,
            quality=quality_info,
            declarations=declarations,
            detected_commodity_name=comm,
            consumer_notice=CONSUMER_LEGAL_NOTICE,
        )

    except Exception as exc:
        logger.error("Consumer scan processing error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing package image.",
        )
    finally:
        # Transient cleanup: ensure no uploaded consumer files remain on disk
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
