// Pagination component for tables
class TablePagination {
    constructor(options) {
        this.options = {
            container: options.container,
            itemsPerPageOptions: options.itemsPerPageOptions || [5, 10, 25, 50, 100],
            defaultItemsPerPage: options.defaultItemsPerPage || 25,
            onPageChange: options.onPageChange || (() => {}),
            onItemsPerPageChange: options.onItemsPerPageChange || (() => {})
        };

        this.currentPage = 1;
        this.totalItems = 0;
        this.itemsPerPage = this.options.defaultItemsPerPage;
        this.totalPages = 0;

        this.render();
    }

    render() {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        container.innerHTML = `
            <div class="pagination-controls d-flex justify-content-between align-items-center p-3">
                <div class="pagination-info">
                    <span class="text-muted">
                        Showing <span id="pagination-start">0</span>-<span id="pagination-end">0</span>
                        of <span id="pagination-total">0</span> items
                    </span>
                </div>

                <div class="pagination-center d-flex align-items-center gap-2">
                    <button id="pagination-first" class="btn btn-sm btn-outline-secondary" disabled>
                        <i class="bi bi-chevron-double-left"></i>
                    </button>
                    <button id="pagination-prev" class="btn btn-sm btn-outline-secondary" disabled>
                        <i class="bi bi-chevron-left"></i>
                    </button>

                    <div class="pagination-pages d-flex gap-1" id="pagination-pages">
                        <!-- Page buttons will be inserted here -->
                    </div>

                    <button id="pagination-next" class="btn btn-sm btn-outline-secondary" disabled>
                        <i class="bi bi-chevron-right"></i>
                    </button>
                    <button id="pagination-last" class="btn btn-sm btn-outline-secondary" disabled>
                        <i class="bi bi-chevron-double-right"></i>
                    </button>
                </div>

                <div class="pagination-per-page d-flex align-items-center gap-2">
                    <label for="items-per-page" class="mb-0">Items per page:</label>
                    <select id="items-per-page" class="form-select form-select-sm" style="width: auto;">
                        ${this.options.itemsPerPageOptions.map(value =>
                            `<option value="${value}" ${value === this.itemsPerPage ? 'selected' : ''}>${value}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    attachEventListeners() {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        // Navigation buttons
        container.querySelector('#pagination-first')?.addEventListener('click', () => this.goToPage(1));
        container.querySelector('#pagination-prev')?.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        container.querySelector('#pagination-next')?.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        container.querySelector('#pagination-last')?.addEventListener('click', () => this.goToPage(this.totalPages));

        // Items per page selector
        container.querySelector('#items-per-page')?.addEventListener('change', (e) => {
            this.itemsPerPage = parseInt(e.target.value);
            this.currentPage = 1; // Reset to first page when changing items per page
            this.options.onItemsPerPageChange(this.itemsPerPage);
            this.updateDisplay();
        });
    }

    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        this.options.onPageChange(page, this.itemsPerPage);
        this.updateDisplay();
    }

    updatePagination(totalItems, currentPage = null) {
        this.totalItems = totalItems;
        this.totalPages = Math.ceil(totalItems / this.itemsPerPage) || 1;

        if (currentPage !== null) {
            this.currentPage = Math.max(1, Math.min(currentPage, this.totalPages));
        }

        this.updateDisplay();
    }

    updateDisplay() {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        // Update info text
        const start = this.totalItems === 0 ? 0 : (this.currentPage - 1) * this.itemsPerPage + 1;
        const end = Math.min(this.currentPage * this.itemsPerPage, this.totalItems);

        container.querySelector('#pagination-start').textContent = start;
        container.querySelector('#pagination-end').textContent = end;
        container.querySelector('#pagination-total').textContent = this.totalItems;

        // Update navigation buttons
        const prevDisabled = this.currentPage <= 1;
        const nextDisabled = this.currentPage >= this.totalPages;

        container.querySelector('#pagination-first').disabled = prevDisabled;
        container.querySelector('#pagination-prev').disabled = prevDisabled;
        container.querySelector('#pagination-next').disabled = nextDisabled;
        container.querySelector('#pagination-last').disabled = nextDisabled;

        // Update page buttons
        this.renderPageButtons();
    }

    renderPageButtons() {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        const pagesContainer = container.querySelector('#pagination-pages');
        if (!pagesContainer) return;

        pagesContainer.innerHTML = '';

        // Calculate page range to display
        let startPage = Math.max(1, this.currentPage - 2);
        let endPage = Math.min(this.totalPages, startPage + 4);

        // Adjust if we're near the end
        if (endPage - startPage < 4) {
            startPage = Math.max(1, endPage - 4);
        }

        // Add first page and ellipsis if needed
        if (startPage > 1) {
            this.addPageButton(pagesContainer, 1);
            if (startPage > 2) {
                pagesContainer.innerHTML += '<span class="px-2">...</span>';
            }
        }

        // Add page buttons
        for (let i = startPage; i <= endPage; i++) {
            this.addPageButton(pagesContainer, i);
        }

        // Add ellipsis and last page if needed
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                pagesContainer.innerHTML += '<span class="px-2">...</span>';
            }
            this.addPageButton(pagesContainer, this.totalPages);
        }
    }

    addPageButton(container, pageNum) {
        const button = document.createElement('button');
        button.className = `btn btn-sm ${pageNum === this.currentPage ? 'btn-primary' : 'btn-outline-secondary'}`;
        button.textContent = pageNum;
        button.addEventListener('click', () => this.goToPage(pageNum));
        container.appendChild(button);
    }

    reset() {
        this.currentPage = 1;
        this.totalItems = 0;
        this.totalPages = 0;
        this.updateDisplay();
    }
}

// Export for use in other modules
window.TablePagination = TablePagination;