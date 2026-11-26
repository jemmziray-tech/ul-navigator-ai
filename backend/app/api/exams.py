from fastapi import APIRouter, HTTPException, Query, Request, Response
from ..security import limiter
from ..tools.exams import lookup_exam, CODE

router = APIRouter(prefix="/api", tags=["exams"])


@router.get("/exams/{code}")
@limiter.limit("12/minute")
def module_exam(request: Request, response: Response, code: str,
                academic_year: str | None = Query(None, pattern=r"^20\d{2}/\d{2}$"),
                session: str | None = Query(None, pattern=r"^(?i:autumn|spring|summer|repeat|winter)$")):
    code = code.strip().upper()
    if not CODE.fullmatch(code):
        raise HTTPException(422, "Enter a module code such as CS4141")
    response.headers["Cache-Control"] = "no-store"
    return lookup_exam(code, academic_year, session)
